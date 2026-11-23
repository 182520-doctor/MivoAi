# MivoAi UI and Workflow Roadmap

## Product direction

MivoAi is organized around two connected workspaces:

1. **Agent creation workspace**: natural-language intent, model discovery,
   tool execution, task progress and result review.
2. **Short-drama production workspace**: brief, story bible, script,
   breakdown, assets, keyframes, clips, audio and final timeline.

The product should expose task types rather than ComfyUI implementation details.
The upper layer passes ordered arrays and canonical parameters; adapters map
them to ComfyUI nodes or future hosted APIs.

## Reference patterns

- Codex-style workbench: persistent thread navigation, a large execution
  surface, compact runtime context and explicit tool activity.
- Jimeng short-drama flow: start from a story or script, establish character
  identity, break the story into shots, generate clips and finish in an editor.
- Jimeng multimodal references: users identify roles such as character,
  scene, motion and audio instead of selecting graph nodes.

Reference pages:

- https://jimeng.jianying.com/tools/ai-short-drama
- https://jimeng.jianying.com/tools/seedance-2-5-creator-offer
- https://docs.volcengine.com/docs/jimeng-ai/jimeng-ai-video-generation-30-product-introduction?lang=zh
- https://rhtv.runninghub.cn/projects/canvas/me

## Completed iteration

### Workflow library

- MiniMax H3 text-to-image
- MiniMax H3 multi-reference image generation, one to ten images
- MiniMax H3 text-to-video
- MiniMax H3 first/last-frame video
- MiniMax H3 multimodal reference video, nine images, three videos and three
  standalone audio clips
- first-frame extraction
- last-frame extraction
- transparent background removal with the local `rembg` runtime

Reference capacity is dynamic. Unused `LoadImage`, `VHS_LoadVideo` and
`LoadAudio` nodes are removed before submission.

### UI

- Updated global navigation and surface tokens
- Standard workflow cards in the ComfyUI configuration page
- Reference-capacity badges and a compact production-tool row
- Multi-modality test asset selection
- New short-drama director workspace with local project draft, stage rail,
  central stage canvas and Agent assistant rail
- Durable short-drama projects in SQLite with create/list/get/stage-update APIs
- Isolated drama project workspaces for story bible, scripts, breakdown, assets,
  keyframes, shots, audio and exports
- Versioned Brief, story-bible and script documents
- Draft save, approve and immutable approved versions
- Durable episodes, scenes and shots
- Three-column production graph for episode, scene and shot management
- Shot production states: planned, keyframe ready, clip ready and approved
- Character, costume, prop, location and style entities with primary visual,
  up to ten supplemental references, draft/locked states and shot references
- Asset Bible workspace with library picker, upload, reference strip and
  per-shot dependency editor
- Storyboard keyframe workspace that chooses text-to-image or multi-reference
  image generation from the number of shot references
- Real keyframe tasks automatically attach the first result to the shot and
  transition it to `keyframe_ready`
- Shot production workspace that automatically chooses text-to-video,
  multimodal-reference video or first/last-frame video from the available
  shot inputs
- Generated video candidates automatically attach to the shot and transition
  it to `clip_ready`
- Every entity or shot slot binding writes a durable candidate ledger.
  Replacing a primary slot marks the previous candidate `superseded` instead
  of deleting it.
- Keyframe and clip panels expose persisted candidate history after task or
  application reload, with select and reject actions.
- Entity slot cards expose their historical candidates without requiring the
  user to remember asset IDs.
- The Agent receives explicit list/update candidate tools and a tool-runtime
  upgrade so long-lived threads can discover them.
- Durable production runs now persist planned media requests, task IDs, result
  assets and per-item failures for one episode.
- Conversation startup recovery now closes turns whose in-memory stream was
  lost during an API restart. Partial assistant text is retained, the message
  becomes `interrupted`, and the existing Codex Thread can resume with the next
  user message instead of remaining permanently `streaming`.
- ProductionRun creation, start and failed-item retry now run the episode
  preflight again. An
  incomplete plan, missing scene/shot description, or invalid shot reference
  blocks batch asset, keyframe and clip generation before any task is queued;
  warnings remain visible without silently becoming launch blockers.
- Asset-library and task-center media cards now constrain intrinsic image
  dimensions. Browser acceptance at 1440px and 960px reports no horizontal
  overflow on any product route, and production restart no longer serves stale
  CSS chunks.
- Task Center is media-only: text-model/Agent turns remain in conversation
  history and no longer crowd out image, video, audio and processing jobs.
- Agent-side run planning reads the current episode, missing slots, model
  defaults and reference assets to assemble a reviewable task graph.
- Partial runs can retry only failed items; successful shots and their bound
  assets remain untouched.
- The production control room lists runs, item-level progress and explicit
  user-confirmed start, cancel and retry actions.
- Production runs follow the selected episode; the Agent handoff carries the
  exact episode and stage context and asks for a review-only task graph.
- Every stage stores an artifact revision. Script, breakdown, asset, keyframe,
  clip and timeline mutations invalidate older role reviews and user gate
  approvals.
- A stale gate cannot be approved again until the current revision has all
  responsible role reviews; the control room shows the change reason and
  requires re-confirmation.
- Production stages now open directly into the episode workspace without the
  generic stage explanation and full control room consuming the first screen.
- The storyboard stage defaults to an episode-scoped visual board with clip
  thumbnails, duration, prompt excerpts, referenced assets and per-shot AI
  generation entry points.
- Episode assets are visible before the shot queue, and the top-level AI action
  opens a review-only ProductionRun planning request for the current episode.
- Episode scope now loads the authoritative episode audit and shows score,
  blocking error count, warning count and the first concrete issues beside the
  plan. “Agent 处理检查项” carries those current findings into a read/review-only
  request instead of hiding quality problems inside the chat transcript.
- Fine editing remains available as a second mode, and quality gates are folded
  into a lower review drawer.
- Shot prompts are durable per semantic slot. Keyframe and video editors restore
  saved text after navigation/restart and batch planning prefers it over derived
  prompts.
- Entity asset-slot prompts are durable too. Character five-view, location,
  costume, prop and style generation use the saved prompt and expose it in the
  asset editor.
- Asset planning now bootstraps a missing identity image first. Detailed views
  are skipped when the chosen model cannot consume an existing primary image,
  preventing five-view generations from drifting into different faces.
- The asset workspace exposes AI planning for all missing assets in the active
  entity category or only the currently selected entity.
- Storyboard cards expose per-shot user approval. A missing clip cannot be
  approved, and replacing the selected video automatically resets it to
  `clip_ready` for re-review.
- Real browser acceptance approved shot 1 and returned it to `clip_ready`,
  confirming the persisted state, UI refresh and reverse transition.
- Shot status transitions now have an immutable event ledger. Storyboard cards
  show the latest reviewer and time, while Agent can query the complete review
  history including automatic replacement rollbacks.
- Final episode render is disabled until every shot is approved. The backend
  enforces the same rule; unapproved output is possible only through an explicit
  preview request.
- Fine clip editing keeps generation mode, reference count, prompt-save state
  and shot-review state visible beside the generate action, while columns use
  content height instead of stretching into large blank panels.
- Canvas stage scope now uses one content-sized working card. The repeated
  canvas title, duplicate Agent/script actions, separate role column and
  previous/current/next flow band were removed; owner status is a compact strip
  inside the stage card.
- The drama Agent now owns the entire fixed right rail from the top to the bottom
  of the viewport. It has no floating drawer shell, rounded card, shadow or
  resize handle. The left workspace is pushed instead of covered; narrow screens
  stack the Agent panel below the production surface.
- Real FFmpeg extraction of first frame, last frame and AAC audio back into the
  shot aggregate
- Editable episode subtitle cues with persisted in/out times
- Chinese SRT burn-in through FFmpeg libass and the local `SimHei` font
- Offline Chinese TTS through Windows SAPI with per-shot audio binding
- Character entities persist a local voice and speaking rate used by shot TTS
- Final episode rendering consumes the shot audio assets, including generated
  voiceover, while falling back to embedded clip audio when none is bound
- One-click 4× upscale for a selected asset primary image
- One-click RIFE interpolation to 60 fps for a shot clip
- Real four-stem Hybrid Demucs audio separation into bass, drums, other and
  vocals
- Two-pass EBU R128 audio normalization with configurable LUFS target
- Per-frame video background removal to a source-framerate VP9 WebM with a
  verified alpha plane
- Separate `video_processing` capability so matting is not advertised as
  generative video synthesis
- Local Whisper transcription through FFmpeg whisper.cpp, returning editable
  subtitle cues and normalized JSON assets
- One-click shot video upscale to 1080p using Lanczos and light sharpening
- Timeline crossfade transitions with synchronized picture and audio
- Persistent background-music and ambience tracks with dB control and ducking
- Persistent per-shot-relative sound-effect cues with asset, start time,
  duration and independent dB volume
- Real FFmpeg mixing of multiple sound-effect cues, including looping short
  sources, trimming, delayed placement and `amix` integration
- Final timeline rendering preserves the highest source frame rate up to 60 fps
- Agent-visible tools for speech, media processing, drama queries and rendering
- Persistent subtitle presets with custom font size, outline and bottom margin
- Deterministic continuity audit for asset locks, shot dependencies, audio,
  voices and subtitle coverage
- Unified aspect-ratio aliases map public values such as `9:16` to ComfyUI
  combo values such as `9:16 (Portrait Widescreen)`
- Container-responsive drama layout: the Agent rail moves below the stage at
  laptop widths so editing surfaces retain usable width

### UI 2.0 and production readability

- Replaced the visually flat shell with a dark production-navigation rail,
  editorial page hierarchy and a warm paper-and-light workspace canvas
- Turned the two home entries into cinematic studio cards with distinct
  multimodal and short-drama identities
- Unified cards, controls, status pills, media previews and empty states across
  dashboard, Agent chat, media, models, assets and tasks
- Added asset-library search plus type filters for images, video, audio and
  other files
- Added task-center search across prompts, providers, models, task types and
  task IDs, composable with status filters
- Added a third audio mode to the multimodal workbench, including audio upload,
  four-track playback and semantic stem labels
- Increased the smallest operational labels in the drama stage rail, shot
  contract and production controls
- Converted the mobile drama stage rail from an eight-row vertical list into a
  horizontally scrolling stepper that automatically centers the active stage
- Automated browser acceptance covered 8 routes at 1440, 1024, 768 and 390 px:
  no horizontal overflow and no failed HTTP responses
- Real browser interaction acceptance verified 67 assets -> 28 videos -> 12
  filename matches, and 67 tasks -> 18 model matches -> 1 failed match
- Real audio workbench acceptance uploaded one mixed track and received four
  playable outputs labeled drums, vocals, other and bass with no browser errors

## Next iterations

### Iteration 2: Shot video and asset utilities

- [x] Generate first frame, last frame and motion clip from the shot detail
- [x] Automatically choose first/last-frame or multimodal reference video
- [x] Extract clip frames back into the shot when a boundary frame is missing
- Run transparent matting directly from a shot or entity
- [x] Add image upscale action for asset primary images
- Add face/detail restoration for locked assets
- [x] Preserve candidate history and approval instead of overwriting results

### Iteration 3: Dialogue, subtitle and sound

- [x] Extract and normalize clip audio
- [x] Assign voices and speaking rate to character entities
- [x] Generate dialogue with local TTS and bind it to the shot
- Align generated dialogue to shot duration
- [x] Generate editable subtitle cues from shot dialogue
- Transcribe clips with word-level timestamps
- [x] Add ambience, music beds, volume and dialogue-ducking controls
- [x] Add per-shot sound effects and multi-cue automation

### Iteration 4: Episode assembly

- [x] Timeline of shot clips with duration, dialogue and readiness review
- Trim controls and richer transition presets
- Safe-area preview and final composition
- [x] Episode render with normalized clips, audio concat and durable export
- [x] Preserve 60 fps footage through final composition
- [x] Crossfade video and audio transitions with configurable duration
- [x] Export manifests pinned to stage revisions, script documents, entity
  slots and shot media

### Workflow backlog

- face/detail restoration
- learned video super-resolution
- Whisper transcription and SRT generation
- isolated Qwen3-TTS worker with voice cloning and multi-role dialogue
- title cards and safe-area overlays
- multi-track music editing with cue envelopes and fades
- video matting and transparent WebM
- batch storyboard and contact-sheet composition

Each workflow is considered available only after a successful real ComfyUI
test. Templates with missing models or Python dependencies remain visible as
templates but are not advertised to the Agent as usable tools.

## Recommended workflow research backlog

The following utilities are useful, but must not be exposed as tools until
their exact local node/model dependencies pass a real execution test:

1. **Face/detail restoration** for identity-locked drama characters.
2. **Video matting / transparent WebM** for compositing actors over generated
   scenes.
   [x] Implemented and verified with browser canvas alpha sampling.
3. [x] **Speech isolation and vocal removal** using the tested four-stem
   Hybrid Demucs workflow.
4. [x] **Audio loudness normalization** with two-pass EBU R128 before
   episode assembly.
5. [x] **Automatic subtitle transcription with segment timestamps** using the
   local FFmpeg whisper.cpp runtime. Word-level refinement remains future work.
6. **Intelligent reframing and safe-area crop** for converting 16:9 source
   material into 9:16 without cutting faces.
7. **Contact-sheet / storyboard collage** for reviewing many keyframes in one
   image.
8. **Title-card and lower-third composition** driven by structured metadata.

Video file concatenation, transitions, subtitle burn-in, frame extraction,
audio extraction, TTS, upscale and frame interpolation remain outside ComfyUI
because FFmpeg or native Windows services execute them more reliably.

## Short-drama production control plane

The current drama iteration changes the workbench from a form-driven pipeline
into a role-driven production system:

- Eight professional roles are executable contracts: screenwriter, director,
  production designer, costume/makeup, lighting, continuity supervisor, first
  assistant director and editor/sound.
- Every role declares responsibilities, required inputs, deliverables,
  professional checklists and review criteria.
- Stage gates are persisted separately from script approval. Agent role reviews
  are evidence; only an explicit user decision can approve and advance a stage.
- Episode plans persist time, locations, interior/exterior, characters, scenes,
  story beats, visual checks, dialogue checks and continuity risks.
- Characters have five-view and expression slots. Locations have master,
  interior, exterior and lighting slots. Other asset types have their own
  reusable slots.
- Shots persist first frame, last frame, nine-grid, storyboard, video and audio
  slots.
- The Agent can read the role handbook and control room, save drafts, plan
  episodes/assets/shots and record role reviews through controlled tools.
- Generated media can be bound back to entity primary/reference, character
  five-view, location master/interior/exterior/lighting, shot first/last frame,
  nine-grid, storyboard, video and audio slots with media-type validation.
- Asset slots can be generated from the entity's visual description with a
  compatible image workflow. Character views, locations and props use
  role-specific prompts that explicitly suppress text, watermarks and people
  in empty scene plates.
- Keyframe generation now targets first frame, last frame, nine-grid continuity
  or a cinematic storyboard and writes the result into the selected shot slot.
- The drama project defaults to a connected production canvas. Scripts, episode
  breakdown, reusable assets, shots and outputs are visible as five related
  lanes; clicking a node opens the existing detailed editor for that stage.
- Canvas navigation supports pointer-drag panning, Ctrl/Command-wheel zoom,
  zoom controls and view reset. Clicking a node opens a property inspector
  first, so users can inspect readiness and context before entering the editor.
- Production lanes and individual nodes can be repositioned on the canvas.
  Positions are stored per project in local browser layout state and can be
  reset without changing project data. Shot nodes include a contextual shortcut
  that opens keyframe or clip production with that exact shot preselected.
- SVG relationship curves are measured from the live lane geometry and follow
  moved lanes, so the script -> episode -> asset -> shot -> output chain remains
  visible while users organize the canvas.
- The canvas now exposes three explicit working scopes:
  - **Global** shows the connected project pipeline and cross-stage status.
  - **Episode** shows one episode's plan, time/place/characters/scenes/story/
    visual/dialogue checks and that episode's artifact chain.
  - **Stage** shows the current Agent assignment, exact artifact list, role
    owners, review state and previous/current/next deliverables.
- Agent handoff prompts include the selected global, episode or stage scope.
- Stage artifact chips are computed from real documents, episode plans, asset
  slots, shot slots, audio, subtitles and exports, rather than being static
  labels. Current/total counts expose exactly what is still missing.
- The drama shell now uses the requested center/right split: the selected global,
  episode or stage result stays in the center, while a live Codex conversation
  occupies the right panel.
- Embedded Agent threads are scoped by project, episode and stage. A 20-episode
  project keeps each episode's conversation independent instead of mixing all
  turns into one project-wide chat.
- Project, episode and scope IDs are persisted on the session row, not only in
  browser local storage. Conversation history therefore remains attributable
  after cache clearing or restart.
- Completed mutating Agent tools emit a workspace refresh signal. The center
  dashboard reloads documents, episodes, assets, shots and gates as soon as the
  Agent saves, generates, binds, reviews, retries or renders something.
- The drama shell also refreshes its left project/episode navigator and document
  directory from the same signal, so Agent-created episodes do not appear only
  in the center after a manual page reload.
- Every embedded Agent message automatically carries project ID, episode ID and
  stage ID as hidden transport context. Reloaded conversations strip that
  context from the user-visible transcript.
- RunningHub's lighter spatial treatment is now available as the default drama
  canvas theme: pale infinite canvas, translucent production groups, white node
  cards, thin relationship curves and a persistent light/dark toggle.
- Selected nodes open a larger in-canvas inspector card rather than a narrow
  side field; the right column remains reserved for the Agent conversation.
- The script stage now uses a reading-first document workspace inspired by
  RunningHub: episode directory, story-setting / episode-outline / script-body
  tabs, readable scene text, edit toggle, approval state and a single next-step
  action into breakdown.
- Multi-reference video generation now consumes bound nine-grid and storyboard
  assets in addition to character/scene references and boundary frames. Their
  continuity instructions are included in the generated video prompt.
- All business pages use the full remaining app width. Drama uses a stable
  four-zone shell: product navigation, project/episode/stage navigator, live
  result workspace and fixed Agent conversation.
- Marketing-style page headings are removed from active drama projects and
  reduced to compact 48px toolbars elsewhere. The drama canvas auto-fits its
  measured content on first render instead of leaving a fixed blank region.
- Three top-level phases replace the always-visible eight-stage rail:
  script, production asset library and storyboard. Sub-stages live in the
  content header. The Agent rail is a persistent sibling column so it never
  covers or reflows the live production result.
- The “canvas / production” switch preserves focused editing without losing
  cross-stage project context.
- The “draft this stage” action now opens a new Agent conversation with the
  project and stage context instead of showing a disabled placeholder.
- The global drama canvas now has a project-level multi-episode video queue.
  Every episode computes its own plan, asset, keyframe, clip and review
  coverage instead of inheriting project-wide stage gates. Cards expose the
  exact next action, active or awaiting ProductionRun state, missing shot lists
  and a one-click Agent handoff containing the project ID and episode ID.
- Episode-level Agent handoff requires planning only the selected episode and
  stops at a reviewable ProductionRun before any GPU work. This keeps 20-episode
  projects independent while allowing the Agent to locate and fill one
  episode's video gap at a time.
- The current delivery target is complete multi-episode shot-video production.
  Subtitles, NLE editing, dubbing and final packaging remain implemented
  downstream capabilities, but they are not prerequisites for advancing the
  keyframe-to-clip pipeline in this iteration.
- The short-drama interaction model is now review-first. Agent prompts complete
  professional work and self-review before presenting a version. The user's
  primary actions are approve, reject, request a rewrite, confirm a material
  creative fork, or approve GPU/model cost.
- Asset editing surfaces lead with the generated result and the review decision.
  Names, continuity prose, voice and speaking-rate controls move into an
  optional “manual edit” disclosure instead of occupying the default workflow.
- Character assets use one 16:9 character sheet rather than six required image
  slots. The sheet combines head close-up, full front/side/back, expression and
  costume/material detail on one continuous canvas.
- Character review now exposes an Agent-maintained creative profile covering
  want, need, wound, false belief, fear, contradiction, public/private self,
  speech, voice, body behavior and arc. These are review evidence rather than a
  default manual form.
- Episode review exposes structured scene contracts. Each scene records its
  entering value, objectives, obstacle, tactics, beats, turn, exit value,
  subtext and performance/visual/sound strategy, so downstream shots can be
  traced back to a professional dramatic purpose.
- Scene-contract context now feeds Agent ProductionRun prompts and direct
  single-shot keyframe/video generation. First/last frames, nine-grid,
  storyboard and clips no longer rely only on a short shot description.
- Shot directing notes are now persisted separately from prompt overrides:
  scale, angle, movement, lens, blocking, performance, expression, composition,
  lighting, sound, transition and reference notes. Both keyframe and clip pages
  expose this as review evidence and include it in generated prompts.

### Deferred ComfyUI work

The current media workflow set is sufficient for drama production and is
intentionally frozen for this iteration. Track these as later one-off checks,
not a persistent source fingerprint system:

- re-import and manually compare the user's edited workflow files
- face/detail restoration for locked actors
- learned video super-resolution
- contact-sheet/storyboard collage generation
- safe-area reframe and title/lower-third composition
- isolated Qwen3-TTS worker with voice cloning
- word-level subtitle timestamps
- [x] approval history and candidate comparison for every generated asset

Do not run the standard-workflow bulk generator against user-edited files and
do not add a permanent source-change detector.
