const stripe = require("stripe")(process.env.STRIPE_SECRET_KEY);
const crypto = require("crypto");

function generateLicenseKey() {
  const random = crypto.randomBytes(12).toString("hex").toUpperCase();
  const parts = [
    random.slice(0, 4),
    random.slice(4, 8),
    random.slice(8, 12),
  ];
  const data = parts.join("-");
  const sig = crypto
    .createHmac("sha256", process.env.LICENSE_SECRET)
    .update(data)
    .digest("hex")
    .slice(0, 4)
    .toUpperCase();
  return `${data}-${sig}`;
}

async function sendLicenseEmail(email, key) {
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${process.env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: "ChestBot <onboarding@resend.dev>",
      to: email,
      subject: "Your ChestBot License Key",
      html: `
        <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;">
          <h2 style="margin-bottom:8px;">You're all set.</h2>
          <p style="color:#666;">Thanks for purchasing ChestBot. Here is your license key:</p>
          <div style="background:#f4f4f4;border-radius:8px;padding:20px;margin:24px 0;text-align:center;font-size:22px;font-family:monospace;letter-spacing:2px;font-weight:bold;">
            ${key}
          </div>
          <p style="color:#666;">Enter this key when ChestBot asks on first launch.</p>
          <div style="margin:24px 0;">
            <a href="https://drive.google.com/file/d/144ZTuW9deYuQDpDvPy6sG1mGHNvFA71g/view?usp=drive_link"
               style="display:inline-block;background:#FF2D55;color:#fff;padding:12px 24px;border-radius:50px;text-decoration:none;font-weight:600;">
              Download ChestBot &rarr;
            </a>
          </div>
          <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
          <p style="color:#666;font-size:13px;">
            Need help? Contact us at chestbot.support@gmail.com
          </p>
        </div>
      `,
    }),
  });
  return res.ok;
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    return res.status(405).end();
  }

  const sig = req.headers["stripe-signature"];
  let event;

  try {
    const rawBody = await new Promise((resolve, reject) => {
      let data = "";
      req.on("data", chunk => data += chunk);
      req.on("end", () => resolve(data));
      req.on("error", reject);
    });

    event = stripe.webhooks.constructEvent(
      rawBody,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET
    );
  } catch (err) {
    console.error("Webhook signature error:", err.message);
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object;
    const email = session.customer_details?.email;

    if (email) {
      const licenseKey = generateLicenseKey();
      const sent = await sendLicenseEmail(email, licenseKey);
      if (!sent) {
        console.error("Failed to send license email to:", email);
        return res.status(500).json({ error: "Failed to send email" });
      }
      console.log(`License key sent to ${email}: ${licenseKey}`);
    }
  }

  res.status(200).json({ received: true });
};
