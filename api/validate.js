const crypto = require("crypto");

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  let body = req.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch { body = {}; }
  }

  const key = body?.key;

  if (!key) {
    return res.status(400).json({ valid: false, error: "No key provided" });
  }

  const parts = key.trim().toUpperCase().split("-");
  if (parts.length !== 4) {
    return res.status(400).json({ valid: false, error: "Invalid key format" });
  }

  const data = parts.slice(0, 3).join("-");
  const sig = parts[3];

  const expected = crypto
    .createHmac("sha256", process.env.LICENSE_SECRET)
    .update(data)
    .digest("hex")
    .slice(0, 4)
    .toUpperCase();

  if (sig === expected) {
    return res.status(200).json({ valid: true });
  } else {
    return res.status(200).json({ valid: false, error: "Invalid license key" });
  }
};
