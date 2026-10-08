# RAGTrust LinkedIn graphic

Generated with the built-in `image_gen` tool using the imagegen skill. No API-key fallback was used.

Selected asset: `ragtrust-linkedin.png` (1733 × 907 pixels; opaque RGB PNG).

Visual review: all five requested strings are readable and match the brief; the selected image contains no provider logos, fake interface, scores, live-AI claim, or deployment URL. A single targeted edit removed an unrequested GitHub icon. The generated source files were retained in Codex's generated-images directory.

## Generation prompt

```text
Use case: ads-marketing
Asset type: landscape LinkedIn launch graphic / social post cover, approximately 1.91:1 landscape composition.
Primary request: A polished premium editorial technology poster for RAGTrust, a public open-source RAG evaluation workflow. Professional, thoughtful, approachable, with generous negative space and unusually elegant clear typography.
Scene/backdrop: Warm cream paper background with very subtle tactile grain; restrained navy type and forms with one small amber accent.
Subject: An abstract evidence flow: a few tactile lightly textured document/evidence cards connect by fine navy lines into a clean navy shield, then continue into a small group of response cards. The cards are abstract paper objects, with only simple line marks as decoration, not a screenshot or fake software interface.
Style/medium: Sophisticated editorial graphic design with a subtle dimensional paper illustration, crisp shapes, soft ambient shadows, beautifully spaced type, quiet premium finish.
Composition/framing: Wide social cover with ample breathing room. Make the brand name and headline the clear focal points; balance the evidence-to-shield-to-response illustration with the copy. Use a coherent typography hierarchy, aligned text, and safe outer margins. Every text line must remain readable at social-feed size.
Color palette: Cream, deep navy, one restrained amber accent only.
Text (verbatim): "RAGTrust"
"Test your RAG. Inspect the evidence."
"Golden datasets · Evidence checks · RAG response tests"
"Open source · Public demo"
"github.com/Nithin9Krishna/ragtrust"
Typography: Large clear editorial sans-serif brand and headline; smaller but legible supporting lines. Render all five strings exactly, preserving capitalization, punctuation, and the middle dots. RAGTrust is spelled R-A-G-T-r-u-s-t. The GitHub path is Nithin9Krishna/ragtrust. Do not invent or add any other text.
Constraints: Exact text only. No fake interface, no scores or charts, no live AI claims, no provider logos, no website URL, no people, no watermarks. Shield imagery should feel like an abstract brand motif, not a third-party certification. Opaque cream background.
```

## Targeted edit prompt

```text
Use case: precise-object-edit
Asset type: LinkedIn launch poster
Input image: edit target.
Change only one thing: remove the small GitHub cat/logo icon to the left of the repository address at the bottom. Fill that icon's location seamlessly with the existing cream textured background. Keep the repository address where it is. Do not replace the icon with anything.
Preserve absolutely everything else: the landscape framing, all typography and line breaks, every text string, navy/cream/amber palette, paper texture, shield, connector lines, cards, shadows, spacing, and illustration.
The exact existing text must remain unchanged: "RAGTrust"; "Test your RAG. Inspect the evidence."; "Golden datasets · Evidence checks · RAG response tests"; "Open source · Public demo"; "github.com/Nithin9Krishna/ragtrust".
No new logos, no provider logos, no new text, no scores, no UI, no live AI claims.
```
