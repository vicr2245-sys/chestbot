// api/validate.js
// Drop this into your /api folder in the chestbot GitHub repo.
// Vercel will expose it at: https://chestbot.vercel.app/api/validate

const crypto = require("crypto");

const SECRET = process.env.LICENSE_SECRET;
const PREFIX = "CB";

function verifyKey(key) {
  // Expected format: CB-<nonce>.<sig>
  if (!key || !key.startsWith(`${PREFIX}-`)) return false;

  const inner = key.slice(PREFIX.length + 1); // strip "CB-"
  const dotIndex = inner.indexOf(".");
  if (dotIndex === -1) return false;

  const nonce = inner.slice(0, dotIndex);
  const providedSig = inner.slice(dotIndex + 1);

  const expectedSig = crypto
    .createHmac("sha256", SECRET)
    .update(nonce)
    .digest("hex")
    .slice(0, 32);

  // Timing-safe comparison
  try {
    return crypto.timingSafeEqual(
      Buffer.from(providedSig, "utf8"),
      Buffer.from(expectedSig, "utf8")
    );
  } catch {
    return false;
  }
}

module.exports = function handler(req, res) {
  // Only allow POST
  if (req.method !== "POST") {
    return res.status(405).json({ valid: false, error: "Method not allowed" });
  }

  if (!SECRET) {
    return res.status(500).json({ valid: false, error: "Server misconfigured" });
  }

  const { key, machine_id } = req.body || {};

  if (!key || !machine_id) {
    return res.status(400).json({ valid: false, error: "Missing key or machine_id" });
  }

  const valid = verifyKey(key);

  if (!valid) {
    return res.status(200).json({ valid: false, error: "Invalid license key" });
  }

  return res.status(200).json({ valid: true });
};
