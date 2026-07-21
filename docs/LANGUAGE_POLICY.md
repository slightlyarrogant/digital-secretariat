# English-only product language policy

## Normative rule

**Every product-owned surface and artifact must be written and delivered in English.** This is a
release requirement, not a stylistic preference.

The rule covers:

- application navigation, labels, actions, empty states, errors, notices, tooltips, and emails;
- product name treatments, page titles, headings, metadata, and filenames intended for users;
- installer prompts, terminal output, installation logs, support handoffs, and operational alerts;
- documentation, screenshots, deterministic demo data, sample conversations, and test fixtures
  visible in product captures;
- every product film title, on-screen label, voiceover, caption, subtitle, description, thumbnail,
  and call to action;
- marketing, sales, hackathon, investor, and partner materials.

## Allowed non-English content

Non-English text is allowed only when it is external data that the product is processing, such as a
customer email or document, or when it is an isolated localization test explicitly marked as such.
It must never become the surrounding interface language or the default demo language.

## Release gate

A release owner must review all rendered routes, email templates, installer output, screenshots,
video frames, captions, metadata, and narration. Any product-owned non-English string blocks the
release. Machine translation without human review does not satisfy this gate.

The `0.1.0` source extraction contains legacy Polish UI and template strings. They are known debt,
not an exception to this policy. The next product release must translate them and add automated
coverage that prevents regression.
