# ComfyUI 工作流模型管理

日期：2026-11-22

## Whisper 兼容补丁

本机 `comfy-mtb` 的 `MTB_AudioToText` 仍读取已废弃的
`WhisperConfig.max_length`。当前 Transformers 版本改用
`max_target_positions`，因此已将该单行读取改为：

```python
getattr(model.config, "max_target_positions", 448) or 448
```

补丁文件位于 ComfyUI 安装目录：

```text
E:\comfyui_decp\custom_nodes\comfy-mtb\nodes\audio.py
```

补丁已通过 Python 语法编译。完整转录实测需要在保存 ComfyUI 当前未保存工作流后，
通过 Comfy Desktop 的受控重启入口重新加载自定义节点。

## 目标

不再写死图像和视频工作流。系统从本地 ComfyUI 用户目录发现工作流，转换成 API
格式，识别可配置输入和输出节点，测试通过后注册成模型供创作页选择。

## ComfyUI API

当前版本使用以下接口：

```text
GET  /userdata?dir=workflows
GET  /userdata/workflows%2F<filename>
GET  /object_info
POST /prompt
GET  /history/{prompt_id}
GET  /view?filename=...&subfolder=...&type=output
```

工作流目录默认是 ComfyUI 用户目录下的 `default/workflows`。平台后端通过 ComfyUI
HTTP API 读取，不直接依赖某个绝对磁盘路径。

## 导入流程

1. 扫描工作流文件名；
2. 读取 UI 格式工作流 JSON；
3. 展开 UI 子图，并重映射子图输入、输出和内部连线；
4. 使用 `/object_info` 补齐 UI 文件中省略的标量输入；
5. 将节点和连线转换为 ComfyUI API Prompt Graph；
6. 生成完整输入目录，包括节点标题、字段、类型、当前值、下拉选项和连线状态；
7. 尽力提供提示词、宽高、种子等建议参数，但不因识别失败阻止导入；
8. 注册为不可直接修改底层图的工作流模型；
9. 模型初始状态为未测试且不启用；
10. 用户调整参数配置并执行测试；
11. 测试成功后启用模型并出现在创作页模型选择器中。

## 由用户设计参数

不同作者会使用完全不同的自定义文本编码、分辨率、采样和素材节点。系统不要求
用户采用某一种工作流模板，而是把所有可配置输入交给用户在 `/models` 中选择。

用户可以为任意节点字段创建参数，例如：

- 把 `Text (user_prompt) / value` 绑定为 `prompt`；
- 把 `Resolution Selector / megapixels` 绑定为 `megapixels`；
- 把 `KSampler / seed` 绑定为 `seed`；
- 把多个 `LoadImage / image` 绑定成一个多素材参数；
- 把模型加载节点的下拉选项绑定为可切换的模型名称。

参考素材不是一种固定参数。用户可以分别创建“图片参考”“视频参考”
“音频 / 语音参考”和“文件参考”，每个参考参数拥有自己的：

- 参数 key 和显示名称；
- `assetType`：`image`、`video`、`audio` 或 `file`；
- 最少、最多文件数量；
- 一个或多个 ComfyUI 节点字段绑定。

生成页会为每个参考参数显示独立上传区和素材预览。上传顺序按该参数的绑定顺序
写入节点，例如第一个视频写入 `VHS_LoadVideo.video`，第二个视频写入另一条
视频字段。多个图片、视频和音频参数不会互相混用。

导入时自动生成的参数只是建议配置。自动识别不到提示词时，工作流仍然会保存为
未测试草稿，用户在“设计参数”中手动选择真实输入即可。

自动生成的参数至少可能包含：

- `prompt`：正向提示词；
- `negativePrompt`：独立反向提示词节点存在时才生成；
- `width` / `height`：宽高；
- `seed`：随机种子；
- `count`：批量数量；
- `length` / `fps`：视频帧数和帧率；
- `assets`：动态参考素材列表。

每个参数包含：

```json
{
  "key": "width",
  "label": "宽度",
  "type": "integer",
  "required": true,
  "default": 1024,
  "min": 64,
  "bindings": [{"nodeId": "58", "field": "width"}]
}
```

用户可以在模型中心新建、删除参数，编辑 key、显示名称、默认值、类型、是否必填、
数值范围和下拉选项，并可为一个参数添加多个工作流字段绑定。修改结果同时写入
工作流记录和模型配置，生成页只读取已配置的参数契约。

管理页面按照 ComfyUI 的使用方式提供工作流地图：

- 默认只展示工作流第一层，子图保持为单个聚合节点；
- 顶层节点使用工作流原始坐标和尺寸摆放；
- 节点之间按 API 图连线绘制 SVG 曲线；
- 当前已经用于生成页的节点会高亮；
- 点击地图节点后，参数小卡片直接出现在节点右侧；
- 画板只用于定位，不在画板上直接编辑节点；
- 点击子图节点时，只展示它在 ComfyUI 顶层已经提升出来的控件；
- 用户点击“启用此参数”即可把该控件加入生成页，不需要先理解 key 或 binding；
- `LoadImage.upload` 这类 UI 操作控件会被忽略，只暴露真正可由 API 赋值的字段；
- 工作流地图、控件目录和参数配置共同保存在导入快照中。

保存参数时后端会验证：

- 参数 key 唯一且非空；
- 每个参数至少绑定一个真实存在的节点字段；
- 同一底层字段不能被多个参数重复绑定；
- 素材参数每个绑定必须有序号；
- 数值最小值不能大于最大值；
- 修改参数后模型回到未测试状态并自动停用，避免旧测试结果错误复用。

## 动态多素材

转换器会扫描标准图片、视频和音频加载节点，并生成建议素材参数：

```json
{
  "key": "assets",
  "type": "assets",
  "assetType": "image",
  "min": 2,
  "max": 4,
  "bindings": [
    {"assetIndex": 0, "nodeId": "12", "field": "image"},
    {"assetIndex": 1, "nodeId": "18", "field": "image"}
  ]
}
```

视频参考形如：

```json
{
  "key": "videos",
  "label": "动作参考",
  "type": "assets",
  "assetType": "video",
  "required": true,
  "min": 1,
  "max": 2,
  "bindings": [
    {"assetIndex": 0, "nodeId": "12", "field": "video"},
    {"assetIndex": 1, "nodeId": "18", "field": "video"}
  ]
}
```

运行时只上传该参数选中的文件，并按 `assetIndex` 填入对应字段。素材数量少于
`min`、多于 `max` 或缺少其他必填参数时，平台会在提交 ComfyUI 前返回明确错误，
避免任务进入排队后卡住。

ComfyUI 的 `/upload/image` 接口实际也支持视频和音频文件，本机已用 MP4 文件验证
返回 `200` 和有效文件名。平台本地素材上传限制为单文件 500 MB，并保留常见图片、
视频、音频、字幕和文本文件扩展名。

## 不直接信任工作流

UI 子图会被展开；无法解析的节点输入不会阻止普通节点导入，但不会出现在可绑定
输入目录中。以下情况仍会明确报错：

- API 图没有任何可执行节点；
- 没有本地图片/视频输出节点；
- 工作流连线缺失或子图输入输出无法映射；
- 视频工作流只有动态 WebP 输出；
- ComfyUI 节点校验返回模型文件缺失、输入非法或节点错误。

模型文件缺失不会静默下载。错误会保存在测试结果中，便于用户修正 ComfyUI 环境。

## API

```text
GET   /api/comfy/workflows
POST  /api/comfy/workflows/import
GET   /api/comfy/workflows/{workflow_id}/inputs
POST  /api/comfy/workflows/{workflow_id}/test
PATCH /api/comfy/workflows/{workflow_id}?enabled=true|false
PUT   /api/comfy/workflows/{workflow_id}/parameters
POST  /api/assets/upload
```

导入请求：

```json
{
  "filename": "image_qwen_image.json",
  "name": "Qwen Image 本地模型",
  "capability": "image_generation"
}
```

## 模型注册

每个导入工作流生成：

- `comfy_workflows` 记录：源文件、API 图、绑定、输出节点、测试状态；
- `models` 记录：展示名称、图片/视频能力、启用状态和公开模型 ID；
- `models.config_json`：工作流 ID、图快照和绑定快照。

创作任务路由到该模型时，Provider Adapter 复制图快照并注入用户提示词和参数。
原工作流文件后续变化不会静默改变已注册模型，必须重新导入生成新快照。

## 上层 API 契约

创作 API 不暴露 ComfyUI 的 `nodeId`、`field` 或槽位绑定。上层只传业务语义：
提示词、业务参数，以及按模态分组的素材数组。

```json
{
  "providerId": "comfyui",
  "modelId": "comfy-wf-...",
  "taskType": "image_generation",
  "prompt": "生成三个人物站在同一场景中的电影画面",
  "images": ["asset-a", "asset-b", "asset-c"],
  "videos": [],
  "audios": [],
  "files": [],
  "parameters": {
    "aspectRatio": "16:9",
    "seed": 42
  }
}
```

调用方不需要知道第一张图片写到哪个 `LoadImage`。工作流适配器会按照已保存的
业务素材参数和内部绑定顺序完成映射。旧字段 `inputAssetIds` 继续兼容，并视为
`images`。

`GET /api/models` 返回的公开模型契约同样不包含底层 bindings：

```json
{
  "parameters": [
    {
      "key": "aspectRatio",
      "label": "画面比例",
      "type": "string",
      "required": true,
      "options": ["16:9", "9:16", "1:1"]
    }
  ],
  "references": [
    {
      "type": "image",
      "label": "参考图片",
      "required": true,
      "min": 1,
      "max": 3
    }
  ]
}
```

后续接入 GPT Image 等收费模型时，只需在新的 Provider Adapter 中把同一组
`images`、`videos`、`audios`、`files` 转换为供应商请求，不需要修改上层
Agent、创作 API 或前端调用方式。

### 统一语义参数

工作流内部字段通过 `semanticKey` 映射到固定语义，上层不直接传节点字段：

| 统一语义 | 可识别的内部别名示例 |
|---|---|
| `prompt` | `prompt`、`replace`、`Text ... prompt` |
| `negativePrompt` | `negative`、`negative_prompt`、反向提示词 |
| `aspectRatio` | `aspect_ratio`、`ratio`、宽高比 |
| `resolution` | `megapixels`、像素、分辨率 |
| `width` / `height` | 宽度、高度 |
| `seed` | `seed`、`noise_seed`、随机种子 |
| `count` | `batch_size`、数量 |
| `duration` / `length` | 时长、视频帧数 |
| `fps` | 帧率 |

上层统一传：

```json
{
  "parameters": {
    "aspectRatio": "16:9",
    "resolution": "2K",
    "seed": 42
  }
}
```

如果内部工作流使用 `megapixels`，`2K` 会在适配器内转换为约 4 MP。
如果内部工作流使用宽高，工作流管理页面会隐藏这两个派生字段，由
`aspectRatio + resolution` 自动计算。实测 `2K + 16:9` 会转换为
`2752 × 1536`。模型管理页面的“高级设置”也允许用户手动修改语义角色。

## 管理页面

`/models` 提供：

- 扫描和搜索 ComfyUI 工作流；
- 设置导入名称与图片/视频能力；
- 导入并注册；
- 使用测试提示词执行真实工作流；
- 显示测试图片或视频；
- 启用/停用模型；
- 分别设置默认文本、图片和视频模型；
- 查看全部节点输入并可视化设计模型参数；
- 为一个参数选择多个节点字段或素材槽位；
- 一键创建图片、视频、音频或以文件为载体的参考输入；
- 在 `/media` 选择任意已启用的图片或视频模型。

## 新版 ComfyUI 控件兼容

新版 ComfyUI 会把控件保存为 `widgets_values_named` 对象，并为
`COMFY_DYNAMICCOMBO_V3` 动态组合框生成额外字段。导入器现在会：

- 同时读取旧数组 `widgets_values` 和新版命名对象；
- 用 `/object_info` 校验命名值是否符合 INT、FLOAT、BOOLEAN、COMBO 类型与选项；
- 当命名值错位时回退到原始数组，并保留节点的合法默认值；
- 支持 `sampling_mode` 这类新版动态组合框；
- 按节点当前真实输入顺序解析 VHS 的动态 `pix_fmt/crf/trim_to_audio` 等控件。

这解决了工作流在 ComfyUI 中打开并再次保存后，`cfg` 变成 `"euler"`、
`sampler_name` 变成 `"simple"`、VHS `crf` 变成 `false`、动态采样模式丢失等
问题。修改工作流文件后仍需重新导入以更新数据库快照，系统不会静默替换已注册图。

## 当前边界

- 暂不自动安装缺失节点或模型；
- 标准 `LoadImage`、`LoadVideo`、`VHS_LoadVideo`、`LoadAudio` 和
  `VHS_LoadAudio` 会自动标记素材类型；
- 非标准自定义加载节点仍可由用户手动选择字段并设置为素材引用，若节点不接受
  ComfyUI 本地文件名，需要在测试时暴露该节点的真实输入要求；
- 网络上传类云端输出节点不优先支持；
- 扩展型动态控件若未在 `/object_info` 中暴露稳定输入类型，可能无法作为参数绑定；
- 非标准外部 API 节点需要对应本地适配器，不能由普通 ComfyUI 图自动替代。
