import {
  Image as ImageIcon,
  Lightbulb,
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
    icon: Video,
    title: "短片故事",
    detail: "从故事梗概到分镜节奏",
    prompt: "和我一起头脑风暴一个短片故事",
  },
  {
    icon: WandSparkles,
    title: "灵感扩写",
    detail: "延展更多可执行的方向",
    prompt: "请基于我的想法延展三个不同的创意方向",
  },
];

export const galleryItems = [
  {
    className: "art-one",
    label: "雪山叙事",
    prompt: "帮我构思一个发生在雪山中的电影感故事",
  },
  {
    className: "art-two",
    label: "玻璃花语",
    prompt: "设计一组透明玻璃花的视觉概念",
  },
  {
    className: "art-three",
    label: "太空伙伴",
    prompt: "构思一个猫咪宇航员的短片创意",
  },
  {
    className: "art-four",
    label: "未来绿洲",
    prompt: "设计一个未来生态城市的世界观",
  },
];
