# Caption timing benchmark

Scripts and sample clips used to check how well the .srt captions follow the voice. The clips are synthesized speech, so real recordings will differ, and every figure here is an estimate from one clip.

Run each script from the repo root with the project's virtual environment, for example `venv\Scripts\python.exe marketing\benchmark\run_timing.py`. They load the default small Whisper model on CPU, so the first run needs the model downloaded.

## Files

`sample_episode.wav` is a 47 second labeled clip with names (Priya Raghunathan, Oluwaseun Adeyemi), jargon (Kubernetes, PostgreSQL), a 50 word sentence, numbers, deliberate pauses and a short closing "Thanks." It is the clip behind the reported results.

`sample_fast.wav` is 13 seconds of fast speech with no pauses, and `sample_fast_words.tsv` holds the seconds and word the speech engine reported for each word of it.

`run_benchmark.py` measures model load time, processing time, word error rate against the known script, and how many names come out right with and without a custom vocabulary. It writes `sample_episode_no_vocabulary.srt` and `sample_episode_with_vocabulary.srt`.

`run_timing.py` compares the older even split of caption cards with the word timed split on the first clip, measuring how far each card start is from the moment the voice resumes after a pause. It writes `sample_episode_word_timed.srt`.

`run_fast_speech.py` checks word start times and card starts on the fast clip with no pauses. The speech engine's own clock runs slow against the audio it writes, so the script rescales it once, using the audible start and end of the speech and not Whisper's times, before comparing. That removes a constant scale and nothing else, which is why the result is an estimate.

## Results on the reference machine

On the 47 second clip with the default model on CPU, processing took about 12 seconds, about 0.27 times real time, and word timestamps added almost nothing. With a four term vocabulary all six names and terms came out right, against three of six without it. The worst card start was 8.2 seconds away from the voice with the even split and 1.3 seconds with word timed cards, and the longest card on screen went from 9.4 to 6.6 seconds. On the fast clip, word start times were within about 0.1 seconds at the median and 0.25 at the worst, and word timed cards were no better than the even split there.

## Limits

One synthesized voice per clip, a single machine, and no overlapping speakers, music or noise. Remaining timing error comes mostly from Whisper's own word alignment.
