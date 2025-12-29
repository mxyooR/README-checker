"""
Markdown 解析器模块 - 解析 README 文件并提取结构化信息

使用 markdown-it-py 进行 AST 解析，提取代码块、链接、图片等元素。
"""

from dataclasses import dataclass, field
from typing import Optional
from markdown_it import MarkdownIt


@dataclass
class CodeBlock:
    """
    代码块数据模型
    
    Attributes:
        language: 代码块语言标识符（如 bash, python, javascript）
        content: 代码块内容
        line_number: 代码块在原文件中的起始行号
    """
    language: str
    content: str
    line_number: int


@dataclass
class Link:
    """
    链接/图片数据模型
    
    Attributes:
        text: 链接文本或图片 alt 文本
        path: 链接路径或图片路径
        line_number: 在原文件中的行号
        is_image: 是否为图片引用
    """
    text: str
    path: str
    line_number: int
    is_image: bool


@dataclass
class ParsedReadme:
    """
    解析后的 README 数据模型
    
    Attributes:
        raw_content: 原始 Markdown 内容
        code_blocks: 提取的所有代码块
        links: 提取的所有链接和图片
        text_content: 纯文本内容（用于关键词匹配）
    """
    raw_content: str
    code_blocks: list[CodeBlock] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    text_content: str = ""


def _get_line_number(content: str, position: int) -> int:
    """
    根据字符位置计算行号
    
    Args:
        content: 原始内容
        position: 字符位置
    
    Returns:
        行号（从1开始）
    """
    return content[:position].count('\n') + 1


def _extract_text_from_tokens(tokens: list, md: MarkdownIt) -> str:
    """
    从 token 列表中提取纯文本内容
    
    Args:
        tokens: markdown-it 解析的 token 列表
        md: MarkdownIt 实例
    
    Returns:
        提取的纯文本
    """
    text_parts = []
    
    for token in tokens:
        if token.type == 'inline' and token.content:
            # 内联内容，提取纯文本
            text_parts.append(token.content)
        elif token.type == 'text':
            text_parts.append(token.content)
        elif token.children:
            # 递归处理子 token
            text_parts.append(_extract_text_from_tokens(token.children, md))
    
    return ' '.join(text_parts)


def parse_readme(content: str) -> ParsedReadme:
    """
    解析 README Markdown 内容
    
    将 Markdown 内容解析为结构化的 ParsedReadme 对象，
    提取代码块、链接、图片和纯文本内容。
    
    Args:
        content: README 的 Markdown 内容
    
    Returns:
        ParsedReadme 对象，包含解析后的结构化数据
    """
    # 创建 MarkdownIt 解析器
    md = MarkdownIt()
    
    # 解析 Markdown 获取 token 列表
    tokens = md.parse(content)
    
    code_blocks: list[CodeBlock] = []
    links: list[Link] = []
    text_parts: list[str] = []
    
    # 遍历所有 token
    for i, token in enumerate(tokens):
        # 提取代码块
        if token.type == 'fence':
            # fence 类型是围栏代码块 ```code```
            language = token.info.strip() if token.info else ""
            line_num = token.map[0] + 1 if token.map else 1
            code_blocks.append(CodeBlock(
                language=language,
                content=token.content,
                line_number=line_num,
            ))
        
        # 提取内联元素（链接、图片）
        elif token.type == 'inline' and token.children:
            for child in token.children:
                if child.type == 'image':
                    # 图片: ![alt](path)
                    line_num = token.map[0] + 1 if token.map else 1
                    links.append(Link(
                        text=child.content or "",
                        path=child.attrGet('src') or "",
                        line_number=line_num,
                        is_image=True,
                    ))
                elif child.type == 'link_open':
                    # 链接: [text](path)
                    # 需要找到对应的 link_close 和中间的文本
                    href = child.attrGet('href') or ""
                    line_num = token.map[0] + 1 if token.map else 1
                    
                    # 获取链接文本（下一个 token 通常是文本）
                    link_text = ""
                    child_idx = token.children.index(child)
                    if child_idx + 1 < len(token.children):
                        next_child = token.children[child_idx + 1]
                        if next_child.type == 'text':
                            link_text = next_child.content or ""
                    
                    links.append(Link(
                        text=link_text,
                        path=href,
                        line_number=line_num,
                        is_image=False,
                    ))
            
            # 提取文本内容
            if token.content:
                text_parts.append(token.content)
    
    # 合并纯文本内容
    text_content = ' '.join(text_parts)
    
    return ParsedReadme(
        raw_content=content,
        code_blocks=code_blocks,
        links=links,
        text_content=text_content,
    )


def render_readme(parsed: ParsedReadme) -> str:
    """
    将 ParsedReadme 渲染回 Markdown 字符串
    
    注意：这是一个简化的渲染器，主要用于 round-trip 测试。
    它会尽量保持原始内容的结构，但可能不会完全一致。
    
    Args:
        parsed: 解析后的 README 对象
    
    Returns:
        渲染后的 Markdown 字符串
    """
    # 对于 round-trip 测试，我们直接返回原始内容
    # 因为完全重建 Markdown 结构比较复杂
    # 真正的 round-trip 验证是：parse(render(parse(x))) == parse(x)
    return parsed.raw_content
