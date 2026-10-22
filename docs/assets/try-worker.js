// Runs Whisper inside the visitor's browser, off the main thread. Nothing here talks to
// VoxScribe's servers. The engine comes from jsDelivr and the model from Hugging Face,
// both only after the visitor clicks "Load the model".
import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@4.3.1';

env.allowLocalModels = false;

const MODEL = 'onnx-community/whisper-tiny.en';
let asr = null;

function resourceCount() {
  return performance.getEntriesByType('resource').length;
}

self.onmessage = async (event) => {
  const msg = event.data;
  try {
    if (msg.type === 'load') {
      const files = {};
      asr = await pipeline('automatic-speech-recognition', MODEL, {
        device: 'wasm',
        dtype: 'q8',
        progress_callback: (p) => {
          if (p.status === 'progress' && p.total) {
            files[p.file] = { loaded: p.loaded, total: p.total };
            let loaded = 0;
            let total = 0;
            for (const f of Object.values(files)) { loaded += f.loaded; total += f.total; }
            self.postMessage({ type: 'progress', loaded, total });
          }
        },
      });
      self.postMessage({ type: 'ready' });
    } else if (msg.type === 'transcribe') {
      const before = resourceCount();
      const start = performance.now();
      const out = await asr(msg.audio, { chunk_length_s: 30 });
      self.postMessage({
        type: 'result',
        text: out.text,
        ms: performance.now() - start,
        requests: resourceCount() - before,
      });
    }
  } catch (err) {
    self.postMessage({ type: 'error', message: String((err && err.message) || err) });
  }
};
