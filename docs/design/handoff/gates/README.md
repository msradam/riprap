# Gates

Five scripts, zero dependencies except `behavioral-gate.mjs` (needs
`playwright` + `@axe-core/playwright`). Each one runs right now, with no
design decisions made yet, and exits 0 with a "this is a template, fill
me in" message — try it:

```
node verify.mjs
```

They stay that way until you (the design session) produce a real token
file. Two things are fixed across all of them because they're
accessibility law, not aesthetic choices: WCAG 1.4.3/1.4.11 contrast
ratios (4.5:1 text, 3:1 graphical) and WCAG 2.5.8 target sizes (24px
pointer, 44px touch). Everything else — palette, radius policy, motion
budget, whether there's a dark ground at all — is a blank you fill in
inside each file's clearly marked `CONFIGURE` block, then the gate
enforces your own decision on every future change.

`lib/color.mjs` and `lib/tokens.mjs` are the reusable machinery
underneath: WCAG relative-luminance/contrast math, Rec.601 grayscale
conversion, and a brace-depth-aware CSS custom-property parser. Prefix-
and ground-agnostic — pass your own `--riprap-*` naming, they don't
assume Datum's or anyone else's.

Once you've designed the token layer:

1. Write `tokens/tokens.css` (built) and `tokens/reference.css`
   (hand-typed, the drift gate's source of truth) using your own
   `--riprap-*` (or whatever prefix you choose) custom properties.
2. Fill in each gate's `CONFIGURE` block with your actual token/role
   names.
3. Run `node verify.mjs`. Fix the design, not the gate, until it's
   green. If a gate turns out to encode a wrong assumption once you see
   it against a real design, that's a legitimate finding — fix the gate
   deliberately and say so, don't silently loosen a threshold to get to
   green.
