# VoxScribe Android: design brief (approved)

Direction: the desktop app's identity, adapted to a phone, with dark and light themes. Prototype: `prototype-b.html`. (`prototype-a.html` is the earlier Paper and Ink concept, kept for reference only, not used.)

## What the app is

Hold a button anywhere on the phone, talk, release, and the text is typed where your cursor is. Transcription runs on the device. VoxScribe is not a keyboard: it works with whichever keyboard the phone already uses, through a floating button and an accessibility service that types into the focused text box. The Flutter app is the control room: dictation, insights, settings, setup, and later file import. The floating button and typing service stay native Kotlin and use the same colors and fonts.

## Themes

Follow the system theme by default. Settings has a three-way choice: System, Light, Dark.

Dark (from the desktop app's `main_window.py` tokens)
- background `#121319`, card `#1B1D27`, raised `#22242F`, border `#2B2E3B`, soft border `#242631`
- text `#ECEEF4`, muted `#8B8D9C`
- accent `#3ECF8E`, pressed `#269E69`, accent as text or icon `#3ECF8E`
- amber (transcribing) `#F0A54A`, red (error) `#F0546B`

Light
- background `#F3F4F7`, card `#FFFFFF`, raised `#E9ECF2`, border `#DADDE6`, soft border `#E6E8EF`
- text `#14161C`, muted `#5B5F6E`
- accent fill `#3ECF8E`, pressed `#2DB77C`, accent as text or icon `#0F7A52`
- amber `#94570A`, red `#D4304A`

Rules:
- The bright green is a fill only, always with dark text (`#0B2418`) on it. Anywhere the accent is text, an icon, or a thin line on the page background, use the darker "accent as text" value so contrast holds in light mode.
- The desktop's faint grey (`#5C5E6C`) fails contrast as text. Use muted for all small text. Faint is decoration only.

## Type

Inter. Scale: 12 labels (bold, uppercase, spaced), 13 meta, 15 list text, 17 transcript and body, 28 screen title, 52 hero number. Numbers use tabular figures. Bundle the font as an asset, no network fetch.

## Structure (same as desktop)

- Bottom tabs: Dictation, Insights, Settings, with Lucide-style line icons.
- Dictation: app bar (green bar mark, wordmark, language chip), status pill, Transcript card with Save, Copy, Clear, Today list, model note, and a pinned green hold-to-dictate button above the tabs.
- Insights: all-time words (hero), words per minute, streak, weekly bars, longest dictation.
- Setup: one card per step (microphone, Accessibility, floating button), current step outlined in green, privacy note.
- No big gradient hero banner (it costs too much phone screen).

## States every screen must handle

Loading model, model download in progress, ready, recording, transcribing, nothing heard, mic permission denied, mic unavailable (Bluetooth dropped), text held because the window changed, offline (normal, never an error), empty history.

## Motion

- Press: 80 ms color shift on the button, a 1.5 percent scale down. Nothing else bounces.
- Recording: a small level meter inside the status pill follows the real input level.
- Transcribing: the text types into the card with a caret. No spinner.
- Haptics: one short tick on press and one on release.
- Reduced motion: no typing animation, meter becomes static.

## Rejected on purpose

Glow and blur effects, gradient banners, a centered pulsing mic circle, identical stat-card grids with decorative icons, emoji, lorem ipsum, white text on the bright green.

## Voice and copy

Plain and short. Say what happened and what to do. Offline is normal and is never shown as a problem. Nothing claims more than the app does.

## Accessibility

- Text contrast: main text above 14:1, muted text above 5:1 in both themes, accent text above 4.9:1, amber text above 5:1 in light.
- State is never color alone: recording also changes the label and gives a haptic; errors use text.
- Hold-to-talk needs an alternative for people who cannot hold: a tap-to-toggle mode in Settings.
- Touch targets at least 48dp. The record button is 60dp tall.

## Flutter notes

Single theme file with two ThemeData objects built from the tokens above. Mirror the same values into Kotlin `colors.xml` (and `values-night`) for the floating button. Custom painter for the level meter and weekly bars.
