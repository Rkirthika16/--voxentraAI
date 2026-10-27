/**
 * Client-side Instant Language Detector for VoxentraAI
 * Immediately recognizes Tamil, Tanglish, and English without network roundtrips.
 */

const TANGLISH_PATTERNS = [
  /\b(vanakkam|வணக்கம்|enga|enga|anga|unga|inda|indha|andha|inga|ippo|eppo|eppo|eppavum)\b/i,
  /\b(thanni|thanneer|salai|theru|kuzhai|kuppai|saakada|saakkadai|sandhu|vilakku|min|current|power)\b/i,
  /\b(varala|varla|varadhu|varuthu|eriyala|erila|adhu|idhu|enakku|ungalluku|namma|ooru)\b/i,
  /\b(illa|ille|illai|aama|aamanga|seri|sari|saringa|apdiye|kooda|mattum|mattume)\b/i,
  /\b(romba|konjam|periya|chinna|mosam|mosama|problem|issue|complaint|panradhu)\b/i,
  /\b(panna|pannunga|pannidunga|pannalam|sollunga|solren|solreenga|kekkala|kekala)\b/i,
  /\b(irukku|iruku|iruka|irukkaa|irukanga|irundhadhu|irunthathu|aachu|aayiduchu|aayiruchu)\b/i,
  /\b(pakkam|kitta|arugil|opposite|pinnaadi|munaadi|naduvula|corner|lane)\b/i,
  /\b(naala|naatkal|mani|neram|varusham|maasam|varushama|maasama|naalaaga)\b/i,
  /\b(gandhipuram|peelamedu|rs\s*puram|vadavalli|singanallur|saravanampatti|saibaba|town\s*hall|ramanathapuram|kurichi|kuniyamuthur|ondipudur|vellalore|thudiyalur)\b/i,
];

export function detectLanguageFromText(text: string): 'Tamil' | 'Tanglish' | 'English' | '' {
  if (!text || !text.trim()) return '';

  const trimmed = text.trim();

  // 1. Check for Tamil Unicode characters (\u0B80-\u0BFF)
  const tamilMatches = trimmed.match(/[\u0B80-\u0BFF]/g);
  if (tamilMatches && tamilMatches.length >= 2) {
    return 'Tamil';
  }

  // 2. Check for Tanglish keywords & phonetics
  for (const regex of TANGLISH_PATTERNS) {
    if (regex.test(trimmed)) {
      return 'Tanglish';
    }
  }

  // 3. Check for specific Tanglish verb and noun suffixes (e.g. -la, -ku, -oda, -um)
  if (/\b\w+(?:la|ku|oda|aachu|pannunga|sollunga)\b/i.test(trimmed)) {
    return 'Tanglish';
  }

  // 4. English fallback if contains latin letters
  if (/[a-zA-Z]/.test(trimmed)) {
    return 'English';
  }

  return 'Tamil';
}

export function formatLanguageDisplay(lang: string | null | undefined): string {
  if (!lang) return 'Auto (Listening...)';
  const norm = lang.trim().toLowerCase();
  if (norm.includes('auto') || norm.includes('detect') || norm.includes('listening')) {
    return 'Auto (Listening...)';
  }
  if (norm === 'tamil' || norm === 'ta' || norm === 'ta-in') {
    return 'தமிழ் (Tamil)';
  }
  if (norm === 'tanglish') {
    return 'Tanglish (தமிழ் + Eng)';
  }
  if (norm === 'english' || norm === 'en' || norm === 'en-in') {
    return 'English';
  }
  return lang;
}
