const stripe = require("stripe")(process.env.STRIPE_SECRET_KEY);
const crypto = require("crypto");

function generateLicenseKey() {
  return [
    crypto.randomBytes(4).toString("hex").toUpperCase(),
    crypto.randomBytes(4).toString("hex").toUpperCase(),
    crypto.randomBytes(4).toString("hex").toUpperCase(),
    crypto.randomBytes(4).toString("hex").toUpperCase(),
  ].join("-");
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
          <hr style="border:none;border-top:1px solid #eee;margin:24px 0;" />
          <p style="color:#666;font-size:13px;">
            Need help? Reply to this email or contact us at chestbot.support@gmail.com
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
