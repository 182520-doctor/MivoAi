# Zaojing Standard Media Workflows

These workflows expose provider-neutral inputs so the same Agent and drama
pipeline can use local ComfyUI models or future hosted models.

## Standard workflow set

The five standard workflows intentionally keep different task semantics:

1. `mivo_std_minimax_h3_image_t2i.json`: image generation without references
2. `mivo_std_minimax_h3_image_multiref.json`: image generation with 1–10 images
3. `mivo_std_minimax_h3_video_t2v.json`: video generation without references
4. `mivo_std_minimax_h3_video_flf2v.json`: exactly two first/last frames
5. `mivo_std_minimax_h3_video_multiref.json`: video generation with up to
   nine images, three videos and three standalone audio references

Reference workflows reserve maximum capacity, then remove unused `LoadImage`,
`VHS_LoadVideo` and `LoadAudio` nodes and their links before ComfyUI
submission. A three-image request therefore does not require placeholder
assets for unused slots.

## 1. MiniMax H3 image text-to-image

- File: `mivo_std_minimax_h3_image_t2i.json`
- References: none
- Core inputs: `prompt`, `aspectRatio`, `resolution`, `seed`
- Use: character sheets, scene concepts, props, posters and storyboard keyframes

## 2. MiniMax H3 multi-reference image generation

- File: `mivo_std_minimax_h3_image_multiref.json`
- References: one to ten images
- Reference order:
  1. primary character identity
  2. secondary character
  3. costume, hair or key prop
  4. scene and lighting
  5. style reference
  6. composition or camera reference
  7. additional prop
  8. additional reference
  9. additional reference
  10. additional reference
- Core inputs: `prompt`, `images[1..10]`, `aspectRatio`, `resolution`, `seed`

The native ComfyUI node supports up to 100 image references. Zaojing's standard
workflow intentionally caps the UI at ten to keep prompt roles and graph
configuration practical; advanced custom workflows can expose more.
- Use: consistent drama assets, character redesign, scene composition and
  costume transfer

## 3. MiniMax H3 text-to-video

- File: `mivo_std_minimax_h3_video_t2v.json`
- References: none
- Core inputs: `prompt`, `aspectRatio`, `resolution`, `duration`
- Use: first-pass motion, atmosphere clips, action previsualization and
  director-style shot exploration

## 4. MiniMax H3 multi-reference video

- File: `mivo_std_minimax_h3_video_multiref.json`
- References: one or more inputs across images, videos or audio; the standard
  capacity is nine images, three videos and three audio clips
- Image reference order:
  1. character identity
  2. costume, hair or key prop
  3. scene, lighting or visual style
  4. motion, pose or additional detail
- Prompt labels: `<Picture 1>` through `<Picture 9>`, plus the declared video
  and audio inputs
- Core inputs: `prompt`, `images[0..9]`, `videos[0..3]`, `audios[0..3]`,
  `aspectRatio`, `resolution`, `duration`
- Use: character-consistent shots, costume continuity, location continuity and
  dialogue-free drama shots

## 5. MiniMax H3 first/last-frame video

- File: `mivo_std_minimax_h3_video_flf2v.json`
- References: exactly two images
- Reference order:
  1. first frame
  2. last frame
- Core inputs: `prompt`, `images[2]`, `width`, `height`, `duration`
- Use: transitions, camera moves, action starts/ends and storyboard
  interpolation

## Atomic production utilities

These workflows perform deterministic media preparation without generative
inference:

- `mivo_std_remove_background.json`: transparent PNG matting with
  `Image Rembg (Remove Background)`
- `mivo_std_extract_first_frame.json`: extract frame index `0` from a video
- `mivo_std_extract_last_frame.json`: extract the final video frame
- `mivo_std_image_upscale.json`: 4× image upscale with
  `4x-UltraSharp.pth` or `ESRGAN_4x.pth`
- `mivo_std_video_interpolate.json`: RIFE frame interpolation to 60 fps
- `mivo_std_audio_separation.json`: Hybrid Demucs separation into bass,
  drums, other and vocals
- `mivo_std_video_matting.json`: per-frame Rembg with VP9 `yuva420p` output

The extraction workflows use `VHS_LoadVideo` and
`GetImagesFromBatchIndexed`. They are designed for storyboard continuation,
tail-frame reuse, transitions and character/scene asset extraction.

Deterministic image utilities are exposed as `image_processing`, not
`image_generation`: remove background, first/last-frame extraction and image
upscale. This prevents asset-generation selectors and the Agent from treating
an upscaler or matting graph as a text-to-image model. Existing imported rows
are backfilled on application startup without rewriting their graph snapshots.

The standard image upscale test converts a 248×248 source to 992×992. The
standard RIFE workflow accepts a video asset and exposes the model, multiplier
and output frame rate; a real test converted a 12 fps clip to a 60 fps H.264
asset. Video interpolation intentionally ignores embedded audio because VHS
fails on audio-less inputs. The shot's persisted `audioAssetId` is used during
episode assembly, where the final compositor automatically adds silence if no
audio is bound.

The audio-separation workflow accepts one `audios[1]` reference at the public
API boundary. It returns four durable output assets named
`mivo_bass_*.flac`, `mivo_drums_*.flac`, `mivo_other_*.flac` and
`mivo_vocals_*.flac`. A real five-second mixed-audio test completed in the
local ComfyUI runtime and produced all four FLAC files. The model capability is
`audio_processing`, so audio workflows remain separate from image and video
generation semantics.

The video-matting workflow preserves the source frame rate through
`VHS_VideoInfoLoaded` and outputs a video-only transparent WebM. Audio is kept
outside this workflow because VHS fails on audio-less inputs when an audio
output is connected; the drama pipeline already stores clip audio separately.
A real 512×288, 12 fps, 1.416-second clip produced a VP9 WebM with
`alpha_mode=1`. Browser canvas sampling measured 94,674 fully transparent
pixels, 7,048 semi-transparent pixels and 45,734 opaque pixels out of 147,456,
proving the alpha plane is present rather than merely tagged.
Its model capability is `video_processing`, not `video_generation`.

The local deterministic media-processing context also exposes:

- `POST /api/media/processing/extract-audio`: extracts a 192 kbps AAC track
  from a generated video with FFmpeg and registers it in the shared asset
  library.
- `GET /api/media/processing/tts/voices`: lists installed offline voices.
- `POST /api/media/processing/tts`: synthesizes 48 kHz mono WAV speech with
  Windows SAPI and registers it as a shot audio asset.
- `POST /api/media/processing/upscale-video`: normalizes a shot to project
  aspect ratio at 1080p with Lanczos scaling and light detail sharpening.
- `POST /api/media/processing/normalize-audio`: runs two-pass FFmpeg
  `loudnorm` analysis and encoding. The default target is `-16 LUFS`,
  `-1.5 dBTP` and `11 LU`; output is 48 kHz stereo AAC at 192 kbps.
- `POST /api/media/processing/transcribe-audio`: runs the FFmpeg whisper.cpp
  filter and returns normalized subtitle cue objects plus a durable JSON file.

This is intentionally outside ComfyUI because it does not require model
inference. The drama shot persists the resulting `audioAssetId`, so dialogue,
ambient sound and final mixing can consume the same durable artifact.

Episode composition uses the same media-processing boundary. The drama
`POST /api/drama/projects/episodes/{episode_id}/render` use case validates that
all shots have video, then the FFmpeg adapter normalizes every clip to the
project aspect ratio while preserving the highest source rate up to 60 fps,
adds silence when a clip has no audio stream, concatenates video and audio in
shot order, and registers the result as an episode export asset.

The render request can select `transition=none` or `transition=crossfade` with
a duration from 0.1–3 seconds. Crossfade uses FFmpeg `xfade` for video and
`acrossfade` for audio so picture and sound transition together. The final
episode duration is reduced by the transition overlap.

Episodes persist a music track, ambience track and independent dB volumes.
Background tracks are looped, trimmed to program duration and mixed with the
shot audio. Music can use FFmpeg sidechain compression so it ducks beneath
dialogue; ambience remains at a constant configured level.

The episode also persists an ordered list of sound-effect cues. Each cue has an
asset ID, start time, duration and independent volume in dB. FFmpeg loops or
trims the source, delays it onto the episode timeline and mixes all cues with
dialogue, music and ambience through `amix`. The cue list is updated through
the same `PUT /api/drama/projects/episodes/{episode_id}/audio-mix` endpoint.

The current audio path was verified with a real 9.784-second episode: video
remained 1080×1920 H.264 at 60 fps, audio remained 48 kHz stereo AAC, and the
decoded audio-stream SHA256 changed after adding a one-second sound-effect cue
at 2.5 seconds. This proves the cue reached the final mix rather than only
being stored in the database.

Subtitle cues are persisted on the episode and can be edited through
`GET/PUT /api/drama/projects/episodes/{episode_id}/subtitles`. Before rendering,
the media-processing context converts the cues to SRT and burns them with the
FFmpeg `subtitles`/libass filter. The local `SimHei` font is used for reliable
Chinese rendering in the current Windows environment.

Episode subtitle style is also persisted. The UI exposes short-video, cinema
and minimal presets plus custom font size, outline and bottom margin. The
media-processing adapter converts the style into a safe ASS `force_style`
string before burning captions.

The current offline TTS baseline uses `Microsoft Huihui Desktop / zh-CN`.
Qwen3-TTS 0.1.1 and its local 0.6B model are present, but its Transformers
4.57 dependency conflicts with the ComfyUI environment's Transformers 5
stack. It must run in an isolated process/venv; installing it into the Comfy
environment would downgrade Diffusers/HuggingFace dependencies and is not
permitted.

## Next workflow backlog

The workflow library is intentionally paused while short-drama production is
built. Existing ready workflows stay usable, but do not bulk-regenerate or
overwrite user-edited JSON. When work resumes, compare changed files manually
and re-import them one at a time; there is no permanent fingerprint service.

Priority order is based on what the short-drama pipeline needs next:

1. face/detail restoration for locked character assets
2. learned video super-resolution for approved shots
3. [x] whisper transcription with segment timestamps.
4. isolated Qwen3-TTS worker with voice cloning and multi-role dialogue
5. title cards and safe-area overlays
6. multi-track music editing with cue envelopes and fades
7. [x] video matting and transparent WebM for compositing
8. batch consistency checks and contact-sheet review

An item leaves this backlog only after a real ComfyUI execution and a stored
test asset. Merely finding a matching graph in the user workflow folder is not
enough to advertise it as an Agent tool.

## Upper-layer contract

The upper layer passes arrays, never ComfyUI node IDs. The workflow adapter owns
the mapping from array positions to `LoadImage` nodes, autogrow inputs and model
conditioning slots.

Recommended canonical parameters:

| Canonical key | Meaning |
| --- | --- |
| `prompt` | complete creative instruction |
| `images` | ordered reference image IDs |
| `aspectRatio` | `1:1`, `4:3`, `3:4`, `16:9`, `9:16` and other supported ratios |
| `resolution` | `1K`, `2K`, `4K` for image; `480p`, `720p` for video |
| `duration` | video duration in seconds |
| `seed` | optional reproducibility seed |
| `audios` | ordered audio inputs for separation and audio post-processing |

For drama production, asset generation uses workflows 1 and 2. Shot generation
uses workflow 4, while transitions and action continuity use workflow 5.
