// api/stripe-webhook.js
// Listens for Stripe payment events, generates a license key, and emails it to the customer.

const crypto = require("crypto");
const https = require("https");

const LICENSE_SECRET = process.env.LICENSE_SECRET;
const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET;
const RESEND_API_KEY = process.env.RESEND_API_KEY;
const FROM_EMAIL = process.env.RESEND_FROM || "licenses@chestbot.app";
const PREFIX = "CB";
const DOWNLOAD_URL = "https://github.com/vicr2245-sys/chestbot/releases/download/v1.0.0/ChestBot.zip";

// ── Helpers ───────────────────────────────────────────────────────────────────

function generateKey() {
  const nonce = crypto.randomBytes(16).toString("hex");
  const sig = crypto
    .createHmac("sha256", LICENSE_SECRET)
    .update(nonce)
    .digest("hex")
    .slice(0, 32);
  return `${PREFIX}-${nonce}.${sig}`;
}

function verifyStripeSignature(rawBody, signature) {
  const parts = Object.fromEntries(
    signature.split(",").map((p) => p.split("="))
  );
  const timestamp = parts["t"];
  const provided = parts["v1"];

  const payload = `${timestamp}.${rawBody}`;
  const expected = crypto
    .createHmac("sha256", STRIPE_WEBHOOK_SECRET)
    .update(payload)
    .digest("hex");

  // Reject if timestamp is older than 5 minutes (replay protection)
  if (Math.abs(Date.now() / 1000 - Number(timestamp)) > 300) return false;

  try {
    return crypto.timingSafeEqual(
      Buffer.from(expected, "utf8"),
      Buffer.from(provided, "utf8")
    );
  } catch {
    return false;
  }
}

function sendEmail(to, key) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      from: FROM_EMAIL,
      to,
      subject: "Your ChestBot License Key",
      html: `
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
          <h2 style="margin-bottom: 8px;">Thanks for purchasing ChestBot! 🎉</h2>
          <p style="color: #555;">Here's your license key. You'll be asked to enter it the first time you launch the app.</p>

          <div style="background: #f4f4f4; border-radius: 8px; padding: 16px 24px; margin: 24px 0; text-align: center;">
            <code style="font-size: 15px; letter-spacing: 1px; color: #111;">${key}</code>
          </div>

          <table width="100%" cellpadding="0" cellspacing="0" style="margin: 24px 0;">
            <tr>
              <td align="center">
                <a href="${DOWNLOAD_URL}"
                   style="background:#111;color:#fff;padding:12px 28px;border-radius:6px;
                          text-decoration:none;font-size:15px;font-weight:bold;
                          display:inline-block;">
                  Download ChestBot
                </a>
              </td>
            </tr>
          </table>

          <p style="color: #555; font-size: 13px;">
            The zip contains the app, setup guide, and README. Your license key is tied
            to your machine on first use. If you need help, contact our support email.
          </p>

          <p style="color: #555;">— ChestBot</p>
        </div>
      `,
    });

    const req = https.request(
      {
        hostname: "api.resend.com",
        path: "/emails",
        method: "POST",
        headers: {
          Authorization: `Bearer ${RESEND_API_KEY}`,
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(JSON.parse(data));
          } else {
            reject(new Error(`Resend error ${res.statusCode}: ${data}`));
          }
        });
      }
    );

    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

// ── Handler ───────────────────────────────────────────────────────────────────

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const signature = req.headers["stripe-signature"];
  if (!signature) {
    return res.status(400).json({ error: "Missing Stripe signature" });
  }

  // Read raw body from stream — required for Stripe signature verification
  const rawBody = await new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });

  if (!verifyStripeSignature(rawBody, signature)) {
    return res.status(400).json({ error: "Invalid signature" });
  }

  const event = JSON.parse(rawBody);

  // Only act on completed payments
  if (event.type !== "checkout.session.completed") {
    return res.status(200).json({ received: true });
  }

  const session = event.data.object;
  const email = session?.customer_details?.email || session?.customer_email;

  if (!email) {
    console.error("No customer email found in session:", session.id);
    return res.status(200).json({ received: true });
  }

  const key = generateKey();

  try {
    await sendEmail(email, key);
    console.log(`License key sent to ${email}`);
  } catch (err) {
    console.error("Failed to send email:", err.message);
    // Still return 200 so Stripe doesn't retry — log and handle manually if needed
  }

  return res.status(200).json({ received: true });
};

// Tell Vercel not to parse the body — Stripe needs the raw bytes to verify the signature
module.exports.config = {
  api: {
    bodyParser: false,
  },
};
