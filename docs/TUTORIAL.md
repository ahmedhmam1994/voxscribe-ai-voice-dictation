# VoxScribe tutorial

A step-by-step guide to every feature in VoxScribe for Windows. Most things are free. Pro features are marked **(Pro)**. Settings is the left-hand button in the main window; open the window from the tray icon (right-click it, then Show).

Contents

1. [First start](#1-first-start)
2. [Dictate into any app](#2-dictate-into-any-app)
3. [Change the hotkey and the microphone](#3-change-the-hotkey-and-the-microphone)
4. [Language and translation](#4-language-and-translation)
5. [Speech models, speed and GPU](#5-speech-models-speed-and-gpu)
6. [Clean-up, voice commands and "send it"](#6-clean-up-voice-commands-and-send-it)
7. [Custom vocabulary and word replacements](#7-custom-vocabulary-and-word-replacements)
8. [Term packs: medicine, law, business, software](#8-term-packs-medicine-law-business-software)
9. [Teach VoxScribe your voice](#9-teach-voxscribe-your-voice)
10. [Spoken formats](#10-spoken-formats)
11. [Dictation modes](#11-dictation-modes)
12. [Try harder](#12-try-harder)
13. [Notes inbox key](#13-notes-inbox-key)
14. [Read it back and unsure words](#14-read-it-back-and-unsure-words)
15. [Start meeting](#15-start-meeting)
16. [Audio and video to text or captions](#16-audio-and-video-to-text-or-captions)
17. [Library, My words and learned words](#17-library-my-words-and-learned-words)
18. [Fill forms by voice (Pro)](#18-fill-forms-by-voice-pro)
19. [Rewrite assistant (Pro)](#19-rewrite-assistant-pro)
20. [Snippets (Pro)](#20-snippets-pro)
21. [Per-app profiles and the second language key (Pro)](#21-per-app-profiles-and-the-second-language-key-pro)
22. [Code dictation and smart formatting (Pro)](#22-code-dictation-and-smart-formatting-pro)
23. [Command line](#23-command-line)
24. [Privacy, offline mode and disabled apps](#24-privacy-offline-mode-and-disabled-apps)
25. [Startup, look, history, Insights, Settings tips and updates](#25-startup-look-history-insights-settings-tips-and-updates)
26. [Pro license](#26-pro-license)
27. [Troubleshooting](#27-troubleshooting)

---

## 1. First start

1. Run the installer. It needs no admin rights.
2. Start VoxScribe. It sits in the system tray (bottom right, maybe behind the `^` arrow) and shows no window on purpose.
3. The first launch downloads the Whisper speech model (a few hundred MB). This is the only download you cannot skip; after it, dictation works offline.
4. Windows may show "Windows protected your PC" because the app is new and unsigned. Click **More info**, then **Run anyway**.
5. The tray menu has: Show, Settings, Start meeting, Try harder, Welcome, Check for updates, logs, Quit. Closing the window only hides it; **Quit** in the tray menu really exits.

After your first dictation VoxScribe asks once whether to start with Windows. You can change that later (see section 25).

## 2. Dictate into any app

1. Click into any text box: a document, a browser, a chat, an editor.
2. **Hold F9**, talk, **release**.
3. A small pill at the bottom of the screen shows Recording, then Transcribing. The text is typed into the window that has focus.

Notes

- The text is typed key by key, not pasted, so your clipboard is never touched.
- VoxScribe never types into password boxes, and what was said there is kept out of the history.
- The main window also has a **Start Recording** button. It works as a plain toggle: click to start, click to stop.
- The transcript appears in the main window. **Copy**, **Save Transcript** and **Clear** sit under it. Right-click a word to correct it for good (section 7).

## 3. Change the hotkey and the microphone

**Hotkey.** Settings, General, HOLD-TO-TALK HOTKEY. Pick another key from the list (F-keys and a few rarely typed keys). The list is limited on purpose: the hook is global, and a normal typing key would stop working everywhere while VoxScribe runs.

**Microphone.** Settings, Audio, MICROPHONE.

1. Choose your microphone, or leave Auto-detect. Auto-detect skips Stereo Mix and similar inputs that record the PC's playback.
2. Click **Test microphone** and talk. The level bar should move.
3. **Keep microphone ready** avoids clipping the first word, at the cost of the microphone staying open between dictations.
4. **Play a sound when recording starts/stops** is under Audio too.

## 4. Language and translation

- Settings, Speech, DICTATION LANGUAGE: pick one of about 28 languages or Auto-detect.
- The language badge in the main window is clickable, and the tray menu has a Dictation language item, so you can switch without opening Settings.
- **Translate to English** speaks in your language and types English.
- Smaller models make more mistakes outside English. If a language comes out poorly, try Small or larger.

## 5. Speech models, speed and GPU

All in Settings, Speech.

**Speech engine.** Whisper is the default and the fallback for everything. Three more engines are optional, and each is downloaded only when you choose it:

- **Cohere Transcribe:** far better Arabic, and it keeps your dialect.
- **Parakeet:** the most accurate and fastest on English, plus 24 more European languages.
- **Moonshine Arabic:** small and fast.

Pick one and VoxScribe downloads it with a progress bar. Or choose **Automatic** and it uses the best downloaded model for your dictation language. If a model fails, Whisper takes over.

**Whisper model size.** Fast, Balanced (default), and with Pro three more accurate ones including Large turbo. Click **Test speed on this PC** to time each one with your own voice before you pick.

**GPU acceleration.** Tick **Use my NVIDIA graphics card** for a much faster Whisper. It needs a one-time download of about 1.1 GB and falls back to your processor by itself if anything goes wrong.

## 6. Clean-up, voice commands and "send it"

Settings, Text.

- **Clean up filler words** removes "um", "uh", "you know" and filler "like", collapses repeated words and fixes spacing and capital letters. It is rule-based, with no AI service.
- **Voice commands:** say **period**, **comma**, **colon**, **question mark**, **exclamation mark**, **new line**, **new paragraph**, **open quote**, **open paren** and the text gets the symbol.
- Take back what you just typed: **scratch that**, **delete last word**.
- Change it: **capitalize that**, **all caps**, **replace X with Y**.
- **Say "send it" to press Enter** (off by default). Useful at the end of a chat message.

## 7. Custom vocabulary and word replacements

Settings, Text.

**Custom vocabulary** is for names and jargon: type them separated by commas (for example `Kubernetes, PostgreSQL, Ahmed`). They help Whisper hear the word, and the finished text is also corrected to your spelling, so they help the other speech models too.

**Word replacements** fix a word the model gets wrong the same way every time. One per line:

```
cube cuddle => kubectl
my email => me@example.com
```

**Faster way:** right-click a word in the transcript and choose **Always correct "..."**, then type the right spelling.

**Move your lists:** **Export my words...** and **Import my words...** (Settings, Text) save and load your vocabulary, replacements and learned words as one file. The Android app reads the same file, so one file keeps both devices in step.

**Names from the window you are typing into.** Settings, Text, **Use names from the window I am typing into** (on by default). When you start dictating, VoxScribe reads the title of the focused window, such as `Q3 forecast.xlsx - Excel`, and passes distinctive names from it (up to 8) to the speech model as hints. Dictating into a file called `Kowalczyk contract.docx` makes the model far more likely to spell Kowalczyk correctly. Only the title text is read, on this PC, and nothing is stored or sent. Untick the box to turn it off.

**Learn vocabulary from a folder** reads your own documents and adds the unusual words it finds.

## 8. Term packs: medicine, law, business, software

Settings, Text, TERM PACKS.

1. Tick **Medical**, **Legal**, **Business** or **Software and AI**. Each shows how many terms it holds. Nothing is downloaded.
2. Dictate normally. Words such as MRI, metformin, habeas corpus, EBITDA, Kubernetes and PostgreSQL are written correctly, with any speech model. The software pack also repairs rare tool names that sound like ordinary words.
3. **Import a term file...** adds your own list as a plain text file, one term per line (an imported pack has a **Remove** button).
4. **(Pro)** Pick packs per program in Per-app profiles (section 21), for example `winword.exe => packs=legal`.

The packs are starting lists. A doctor or lawyer will want to add their own terms.

## 9. Teach VoxScribe your voice

Settings, Text, **Teach VoxScribe your voice...**

1. Click the button and read the short script (about three minutes) at your normal speed, in your normal voice or accent.
2. VoxScribe compares what it heard with what you read and lists the words it mishears.
3. Tick the fixes you want. They become word replacements from then on.

Recordings stay on this PC.

## 10. Spoken formats

Settings, Text, **Spoken formats for the packs** (off by default).

| You say | You get |
| --- | --- |
| one twenty over eighty | 120/80 |
| five milligrams twice daily | 5 mg BID |
| section twelve subsection b | section 12(b) |
| fifty thousand dollars | $50,000 |
| twenty five percent | 25% |

It follows the term packs you switched on and only rewrites a number that sits next to the unit or word that shows what it is, so ordinary sentences are left alone.

## 11. Dictation modes

Settings, Text, DICTATION MODE. Pick how your words are tidied to fit what you write:

- **Chat:** short, casual.
- **Email:** greetings and full sentences.
- **Code:** for programming text.
- **Notes:** plain notes.

**(Pro)** **Switch modes by app automatically**: chat apps (Slack, Discord, WhatsApp, Teams) use Chat, Outlook and Thunderbird use Email, code editors and terminals use Code, Word, Notion, Obsidian and Notepad use Notes. It is decided from the program's name only, never from the screen.

## 12. Try harder

A word came out wrong?

1. Within 2 minutes, press **F8** (or tray menu, Try harder).
2. The same recording runs again through a bigger model if you have one (Small free; Medium, Large turbo or Large with Pro), or through the same model in careful mode.
3. Only what changed is retyped.

Change the key in Settings, General, TRY HARDER KEY.

## 13. Notes inbox key

For quick thoughts that should not be typed anywhere.

1. Settings, General, NOTES INBOX KEY: choose a key and a **Browse...** folder. A folder inside your Obsidian vault works well.
2. Hold the key and speak, then release.
3. The words are saved as a line with the time in a markdown file in that folder, and nothing is typed.

## 14. Read it back and unsure words

Both are off until you turn them on.

- **Read each dictation aloud** (Settings, General): after each dictation Windows' own voice reads it back, so you can check it without looking. In the transcript, right-click for **Read aloud** or **Read the last line aloud**, and **Stop reading**.
- **Underline unsure words in the transcript** (Settings, Text): words the speech model was not sure about are underlined (Whisper and Parakeet). Check those first.

## 15. Start meeting

Records a meeting or call and writes notes. Everything stays on the PC.

1. Settings, General, **MEETING NOTES FOLDER**: choose where notes go (default `Documents\VoxScribe Meetings`). Point it at your Obsidian vault if you like.
2. Leave **Also record what this PC plays (calls)** ticked to capture the other people. Untick it for a microphone-only recording.
3. Click **Start meeting** in the main window, or use the tray menu. VoxScribe asks you to confirm before it starts. Tell everyone on the call that it is being transcribed: recording other people needs their consent in many places.
4. Talk or join your call. The button turns into a stop button. Normal dictation is paused during a meeting.
5. Click it again to stop. VoxScribe transcribes both tracks, puts them in time order, removes the echo that comes from your speakers, and writes a markdown note with action items, decisions, questions and the full transcript. Your lines are labelled **You**, everyone else **Others**.
6. If you quit during a meeting, VoxScribe asks first. The recording is kept for a week even if no notes were written.

Tip: with headphones there is no echo to remove, and the notes come out cleanest.

## 16. Audio and video to text or captions

1. Open **Files** in the left-hand list. Click **Import Audio** and pick a file, **Import Folder** to do a whole folder, or **Import Link** to paste a web address (see below).
2. Tick **Save .srt captions** to also get a subtitle file next to each source. Captions are capped at two short lines and cut at pauses. An existing caption file is never overwritten.
3. When a folder finishes, a report lists what was saved, skipped and failed, flags cards that look too fast to read, and lets you retry failures in one click.
4. **(Pro)** **Also .vtt, .md, .docx** and **Label speakers**. Name the speakers in Settings, Files, and the names appear in the output.
5. Caption line length and the speaker names are in Settings, Files.

Folder import has 2 free runs, then it is a Pro feature.

**Import Link.** Paste the address of a video or audio page, such as a YouTube video. VoxScribe uses the site's own captions when it has them. If not, it downloads the audio and transcribes it here with your speech model. The first time, it fetches a small download helper (`yt-dlp`) into your VoxScribe folder. The result is saved to the Library (section 17), and as captions if **Save .srt captions** is ticked. Link import gives 3 free tries, then needs Pro. Only import what you have the right to use.

## 17. Library, My words and learned words

Three pages in the left-hand list keep your work together. All of it stays on this PC.

**Library.** Everything you dictated, imported or sent to notes, in one place.

1. Type in the search box ("Search everything you said, imported or noted") to find any of it.
2. Click an item to read it on the right. **Summarize**, **Save**, **Copy** and **Delete** sit above the text.
3. **Keep dictations and file transcripts** sets how long items are kept.

**My words.** How VoxScribe spells for you.

- **Learned from your fixes.** When you correct a word in the transcript, VoxScribe remembers the fix and applies it next time. Untick **Learn from my fixes** to stop, or click **Clear all** to forget them.
- **What you mostly write** and **Where you write most** tell VoxScribe your field and your main apps, so it picks sensible packs and modes.
- **Teach VoxScribe your voice** is the same reading exercise as in section 9.
- **Edit word lists in Settings** opens your vocabulary and replacements (section 7).

**Insights** shows your own statistics, such as words per day (section 25).

## 18. Fill forms by voice (Pro)

Settings, Text, **Fill forms by voice**.

1. Click into the first box of a form on a web page or in an app.
2. Hold the hotkey and say a label then its value for each box: "Name Sam Lee, phone 0100 123 4567, email sam at gmail dot com".
3. Release. VoxScribe types each value into its box and moves on.

It only fills when the sentence starts with a label and names at least 2 boxes, so ordinary dictation is never turned into a form fill by accident. Password boxes are never touched. Form fill gives 3 free tries, then needs Pro.

## 19. Rewrite assistant (Pro)

Say what you want done to the text you just dictated.

1. Settings, Speech, **REWRITE ASSISTANT**: pick a model and click **Download** (an optional download of a few GB; **Change folder...** puts it on another drive, **Remove** deletes it).
2. Dictate as usual.
3. Right after, say **make it formal**, **make it friendly**, **make it shorter**, **bullet points** or **fix the grammar**.

A local language model on your PC rewrites the text, and VoxScribe checks that every number is kept before it replaces what was typed. Nothing leaves the computer. The assistant gives 3 free tries, then needs Pro.

## 20. Snippets (Pro)

Say a short phrase, get a whole block of text.

1. Settings, Pro, SNIPPETS (PRO). One per line:

```
my address => 12 Example Street, Cairo
sign off => Best regards, Ahmed
today is => {date}
paste it => {clipboard}
```

2. Dictate the trigger phrase on its own. The snippet is typed in its place.
3. Variables: `{date}`, `{time}`, `{clipboard}` are filled in live.

## 21. Per-app profiles and the second language key (Pro)

**Per-app profiles.** Settings, Pro. One line per program, matched by its executable name:

```
code.exe => code=on, cleanup=off, language=en
slack.exe => mode=chat, smart=off
winword.exe => packs=legal
```

Options: `mode`, `language`, `cleanup`, `voice_commands`, `code`, `smart`, `period`, `packs` (use `packs=medical+legal`, or `packs=off`). Anything a profile does not set uses your normal setting.

**Second language key.** Settings, Speech, SECOND LANGUAGE KEY (PRO). Hold this key instead of the main one to dictate in your second language, with no trip to Settings.

## 22. Code dictation and smart formatting (Pro)

Settings, Pro, PRO TOOLS.

- **Code dictation:** say the symbols and casing of code ("snake case user name" becomes `user_name`, "open paren x close paren" becomes `(x)`).
- **Smart formatting:** spoken emails, web addresses and numbers are typed the way they are written: "john dot smith at gmail dot com" becomes john.smith@gmail.com, "example dot com slash pricing" becomes example.com/pricing, "one hundred and five dollars" becomes $105. A lone small number is left as a word.

## 23. Command line

The same engine runs from scripts. From a source checkout:

```
venv\Scripts\python.exe cli.py meeting.mp3
venv\Scripts\python.exe cli.py talk.mp4 --format srt --output captions
venv\Scripts\python.exe cli.py interview.m4a --language auto --translate
```

Text goes to stdout or into the `--output` folder (an existing file is never replaced). `--raw` gives text exactly as heard. `.vtt`, `.md` and the three most accurate models need Pro. `cli.py --help` lists every option.

## 24. Privacy, offline mode and disabled apps

Settings, Privacy.

- After each dictation the status line shows how many outside connections were made. Normally zero.
- **Offline mode: block all network use** shuts every connection. Downloads, update checks and pings stop until you turn it off.
- **View connection log** lists every connection the app tried.
- **Send anonymous usage pings** (app version and Windows version only, a random id, never audio or text) can be switched off.
- **DISABLED APPS:** list programs where VoxScribe must do nothing, for example `keepass.exe`.

## 25. Startup, look, history, Insights, Settings tips and updates

- **Start VoxScribe automatically when Windows starts:** Settings, General, STARTUP.
- **APPEARANCE:** Light, Dark or Same as Windows.
- **Today** list in the main window keeps your recent dictations.
- **Insights** (left-hand side) shows your own statistics, such as words per day and the time saved against typing. Settings, About also has STATISTICS.
- **Check for updates** is in Settings, About and the tray menu. Settings and Pro license are kept when you update.

Getting around Settings

- **Search.** Press Ctrl+F in Settings and type what you want ("microphone", "offline"). Press Enter or click a result and VoxScribe jumps to the setting and flashes it.
- **Folded groups.** Long pages are split into groups with a small arrow. Click a heading to fold or open it, or use **Expand all** / **Collapse all**. Long hints show their first sentence with a **More** link.
- **Unsaved changes.** A chip shows "Unsaved changes" and Close becomes **Discard**. If you leave with changes, VoxScribe asks whether to save, discard or keep editing.
- **Save changes** saves and keeps you on the same page, with a green "Saved" note.

## 26. Pro license

Pro is a one-time $14 payment and covers two PCs and two phones. Everything else stays free, with no account.

What Pro adds: form fill, the rewrite assistant and link import (each with 3 free tries), Snippets, fill-in templates, per-app profiles (including per-app term packs), dictation modes that switch by app, Code mode and code dictation, smart formatting, a second language key, the Medium, Large turbo and Large Whisper models (also used by Try harder), folders of files beyond 2 free runs, .vtt, .md and .docx export, and speaker labels.

1. Settings, Pro, **Get Pro ($14 once)**.
2. Paste the license key and click **Unlock**.
3. To move it to a new PC, click **Remove license** on the old one first.

## 27. Troubleshooting

| Problem | Try |
| --- | --- |
| Nothing is typed | Click into a text box first. Check the app is not in DISABLED APPS. Password boxes are skipped on purpose. |
| Silent or very quiet | Use **Test microphone**. Pick your headset or mic by name instead of Auto-detect. |
| First word missing | Tick **Keep microphone ready**. |
| Wrong words | Add them to custom vocabulary, use a term pack, run **Teach VoxScribe your voice**, or press F8 to try harder. |
| Poor accuracy outside English | Use a bigger Whisper model, or Cohere or Parakeet for supported languages. |
| Slow | Pick Fast, switch on GPU, or use Parakeet for English. |
| Meeting has no "Others" | Tick **Also record what this PC plays**. Play audio on the default output device. |
| Import Link says download failed | Check the address opens in a browser and the video is public, then try again. |
| Form fill typed nothing | Start with the box label and name at least 2 boxes. Password boxes are skipped on purpose. |
| Rewrite did nothing | Download the assistant model first (Settings, Speech). Say the command right after a dictation. |
| SmartScreen warning | More info, Run anyway. The installer is unsigned. |

Still stuck? Open an issue: https://github.com/ahmedhmam1994/voxscribe-ai-voice-dictation/issues
