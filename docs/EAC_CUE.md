# Exact Audio Copy CUE output, 0.4.1

CD_READY now contains numbered final PCM WAV files, MegaMix.cue, Verification.csv,
VERIFIED.json and BURN_WITH_EAC.txt. CUE generation is part of the finalization
transaction: a failure prevents new output from being marked Ready.

## Layout

The CUE uses a separate FILE command for each final WAV, followed by its sequential
TRACK nn AUDIO command, TITLE, PERFORMER and INDEX 01 00:00:00. Index times are
relative to their current file, so they are not cumulative disc timestamps.
Every referenced WAV is checked for 44.1 kHz, 16-bit PCM stereo and 588-sample
frame alignment before CUE publication.

Pauses, including preserved source silence, have already been baked into the
audio. No synthetic PREGAP, POSTGAP or INDEX 00 command is emitted. The standard
first-track lead-in is the CD writer's responsibility. The project's pregap
reserve remains a capacity calculation, not extra silence inserted by this CUE.

The disc TITLE is the project name. A common known artist becomes the disc
PERFORMER; multiple distinct known artists produce Various Artists. Track titles
and performers come from the project, with an empty artist left empty. Original
album titles are not used as the compilation title. UPC/CATALOG, ISRC, genre,
date, songwriter, pre-emphasis and copy flags are omitted when not authoritatively
available. This is a newly authored compilation, not a source CD reconstruction.

CD-Text strings normalize embedded quotes to apostrophes, remove control/newline
injection and use at most 80 display characters for conservative CUE compatibility.
The project JSON retains full metadata. FILE references are not CD-Text strings;
they retain the exact sanitized filenames of the actual generated WAV files.

## Load in EAC

1. Keep the CUE and every numbered WAV in the same folder on your Windows PC.
2. Open EAC's Tools > Write CD-R window, then load MegaMix.cue. Dragging the CUE
   onto EAC is another documented way to open its write module.
3. Check track count, order and displayed metadata before writing. Do not append
   the WAVs separately after loading the CUE.
4. Use Disc-At-Once and disable any additional inter-track gap setting. EAC's FAQ
   explains that writing software/TAO can add unwanted two-second gaps.
5. Enable CD-Text if desired and supported by the selected write engine/drive.
   Metadata in a CUE alone does not guarantee that a particular writer records
   it or a player displays it. EAC's documented Unicode support excludes CD-Text.

## Encoding and existing Ready output

Automatic output uses Windows-1252 if all filenames and CD-Text fit, otherwise
UTF-8 with a BOM. Both use explicit CRLF line endings on every OS. The C shortcut
can explicitly select UTF-8 or Windows-1252 for compatibility testing. If that encoding cannot represent a name, generation fails without
silently substituting characters; use UTF-8 instead. Check names in EAC before
burning, especially outside Western European characters. Its native import and
drive-dependent CD-Text behaviour remain untested in this environment.

C requires Ready status, a matching VERIFIED.json identity, matching sample/frame
totals and valid aligned WAVs. It writes a new CUE atomically and records its
filename, encoding, track count and SHA-256 in VERIFIED.json. WAV bytes are not
changed. It can repair a missing CUE or add one to output from version 0.4.0.
Full preparation or stage 3 generates a CUE automatically in new runs.

The headless Cue action accepts an optional request JSON with
`{"encoding":"cp1252"}`, `{"encoding":"utf-8-sig"}` or `{"encoding":"auto"}`. It is invoked with
`--action Cue --project <project.json> --request <request.json>`.

## Sources checked

- Official EAC features, including CUE/CD-Text and writing support:
  https://www.exactaudiocopy.de/features-of-eac/
- Official EAC FAQ, unwanted gaps and DAO:
  https://www.exactaudiocopy.de/faq/
- Official EAC change log, CUE drag/drop and Unicode/CD-Text limitations:
  https://www.exactaudiocopy.de/whats-new/
- GNU ccd2cue CUE command definitions, especially FILE, TRACK, TITLE, PERFORMER,
  INDEX and PREGAP:
  https://www.gnu.org/software/ccd2cue/manual/html_node/CUE-sheet-format.html

The automatic encoding preference is an implementation choice, not a claim that
EAC's public documentation guarantees every CUE encoding. Both encodings are covered
by the generator tests. A real EAC import and physical CD-R burn remain pending.
