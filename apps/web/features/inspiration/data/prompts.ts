import {
  Image as ImageIcon,
  Lightbulb,
  Clapperboard,
  Video,
  WandSparkles,
} from "lucide-react";

export const quickActions = [
  {
    icon: Lightbulb,
    title: "创意策划",
    detail: "把模糊灵感变成清晰方案",
    prompt: "帮我把一个模糊的创意整理成清晰方案",
  },
  {
    icon: ImageIcon,
    title: "画面提示词",
    detail: "设计构图、风格与光影",
    prompt: "为一张产品海报设计画面和提示词",
  },
  {
    icon: Clapperboard,
    title: "导演写剧本",
    detail: "从创意想法到完整剧本",
    prompt:
      "请以导演 Agent 的方式和我一起完成一个短片剧本。先判断我的信息是否足够；如果不足，最多问我 3 个关键问题；如果足够，请输出创意定位、人物设定、故事结构、完整剧本、关键镜头、声音设计和下一步修改建议。我的初始想法是：",
  },
  {
    icon: Video,
    title: "短片故事",
    detail: "从故事梗概到分镜节奏",
    prompt:
      "帮我把一个短片故事从一句话创意发展成故事梗概、人物关系、三幕结构和分镜节奏。",
  },
  {
    icon: WandSparkles,
    title: "灵感扩写",
    detail: "延展可执行方向",
    prompt: "请基于我的想法延展三个不同的创意方向，并说明每个方向适合的剧本风格。",
  },
];

export const galleryItems = [
  {
    className: "art-one",
    label: "雪山叙事",
    prompt:
      "请以导演 Agent 的方式，把“雪山里两个人被困一夜”的创意发展成完整短片剧本。",
  },
  {
    className: "art-two",
    label: "玻璃花语",
    prompt: "设计一组透明玻璃花的视觉概念",
  },
  {
    className: "art-three",
    label: "太空伙伴",
    prompt:
      "请把“猫咪宇航员寻找回家信号”的想法发展成完整短片剧本，包含人物、结构、场景和镜头。",
  },
  {
    className: "art-four",
    label: "未来绿洲",
    prompt: "设计一个未来生态城市的世界观",
  },
];
