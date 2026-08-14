# Notices and attributions

## What this repo does *not* ship

The **HyperFrames** skill pack (`hyperframes-core`, `-creative`, `-animation`, `-cli`, `-registry`,
`-media`, `embedded-captions`, `talking-head-recut`, `faceless-explainer`, `product-launch-video`,
`music-to-video`, `motion-graphics`, `media-use`, and the video orchestrators) is **not vendored
here**. It is maintained upstream and installs itself:

```bash
npx hyperframes skills
```

Reasons: it is third-party work with its own release cadence, it is large (tens of MB of fonts,
motion primitives and vendored JS), and some of its bundled assets carry licences that forbid
redistribution — e.g. a CD Projekt Red fan-kit typeface restricted to non-commercial use. Pulling
it from upstream keeps the licensing where it belongs and keeps this repo small.

## Third-party tools this kit drives (not redistributed)

| Tool | Licence | Role |
|---|---|---|
| [FFmpeg](https://ffmpeg.org) | LGPL/GPL | probe, frames, audio, transcode |
| [OpenAI Whisper](https://github.com/openai/whisper) | MIT | transcription engine |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (CTranslate2) | MIT | default transcription engine |
| [whisper.cpp](https://github.com/ggerganov/whisper.cpp) via `hyperframes transcribe` | MIT | zero-install fallback engine |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Unlicense | downloading recordings |
| [Playwright](https://playwright.dev) | Apache-2.0 | scripted walkthrough recordings |
| [@railsblueprint/blueprint-mcp](https://www.npmjs.com/package/@railsblueprint/blueprint-mcp) | see package | browser automation MCP |

Each is installed from its own distribution channel by the installer; none of their code is copied
into this repository.

## Prior art

`pwa-walkthrough-test` and `video-bug-scan` were written for internal use and generalized here.
`recording-brief` generalizes a Zoom + Blackboard lecture workflow (the personal,
institution-specific original stays out of this repo).

## Usage boundary

The download helpers exist for recordings the operator is entitled to — their own meetings, courses
they are enrolled in, sessions they were invited to. Do not use them to obtain or redistribute
material you have no right to.
