"""
表情包情感映射引擎

分析 AI 回复内容中的情感倾向，返回对应的表情标签（如 [happy]），
客户端可根据标签展示本地表情包。
"""

import re
from typing import List, Tuple

class EmotionEngine:
    def __init__(self):
        # 情感关键词库（可扩展）
        self.emotion_keywords = {
            'happy': ['哈哈', '开心', '笑死', '快乐', '高兴', '嘻嘻', '嘿嘿'],
            'sad': ['难过', '伤心', '哭', '悲伤', '郁闷', '失落'],
            'angry': ['生气', '愤怒', '可恶', '烦', '恼火', '滚'],
            'surprised': ['哇', '天哪', '居然', '真的假的', '震惊', '意外'],
            'love': ['爱你', '喜欢', '想你', '抱抱', '亲亲', '么么哒'],
            'shy': ['害羞', '不好意思', '脸红', '羞涩'],
            'confused': ['不懂', '不明白', '啥意思', '懵逼', '疑惑'],
            'tired': ['累', '困', '疲惫', '休息'],
        }

    def analyze(self, text: str) -> List[str]:
        """
        分析文本，返回匹配到的情感标签列表（可能多个）
        """
        detected = []
        text_lower = text.lower()
        for emotion, keywords in self.emotion_keywords.items():
            for kw in keywords:
                if kw in text or kw in text_lower:
                    detected.append(emotion)
                    break  # 一种情绪只记录一次
        return detected

    def generate_emoji_tag(self, text: str) -> str:
        """
        为 AI 回复生成表情标签，用于嵌入回复文本中
        例如：回复末尾添加 "[happy]"
        """
        emotions = self.analyze(text)
        if emotions:
            # 简单策略：取第一个检测到的情绪
            primary_emotion = emotions[0]
            return f"[{primary_emotion}]"
        return ""

    def enrich_response(self, original_response: str) -> str:
        """
        为原始 AI 回复添加表情标签
        """
        tag = self.generate_emoji_tag(original_response)
        if tag and tag not in original_response:
            return f"{original_response} {tag}"
        return original_response


# 测试示例
if __name__ == "__main__":
    engine = EmotionEngine()
    test_responses = [
        "哈哈，你真是太搞笑了！",
        "我今天心情不太好，有点难过。",
        "哇塞，真的吗？太让人震惊了！",
        "好的，我知道了。",
    ]
    for resp in test_responses:
        print(f"原文: {resp}")
        print(f"增强: {engine.enrich_response(resp)}\n")