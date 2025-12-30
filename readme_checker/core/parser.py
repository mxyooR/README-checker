"""
Markdown 解析器模块 - 解析 README 文件并提取结构化信息

使用 markdown-it-py 进行 AST 解析，提取代码块、链接、标题等元素。
支持 GitHub 风格的 Header ID 生成。
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from markdown_it import MarkdownIt


@dataclass
class Link:
    """
    链接数据模型
    
    Attributes:
        text: 链接文本或图片 alt 文本
        path: 链接路径或图片路径
        line_number: 在原文件中的行号
        is_image: 是否为图片引用
        anchor: 锚点部分（如 #section）
    """
    text: str
    path: str
    line_number: int
    is_image: bool
    anchor: Optional[str] = None


@dataclass
class Header:
    """
    标题数据模型
    
    Attributes:
        level: 标题级别 (1-6)
        text: 标题文本
        id: GitHub 风格的 Header ID
        line_number: 在原文件中的行号
    """
    level: int
    text: str
    id: str
    line_number: int


@dataclass
class CodeBlock:
    """
    代码块数据模型
    
    Attributes:
        language: 代码块语言标识符（如 bash, python, javascript）
        content: 代码块内容
        line_number: 代码块在原文件中的起始行号
    """
    language: Optional[str]
    content: str
    line_number: int


@dataclass
class ParsedMarkdown:
    """
    解析后的 Markdown 数据模型
    
    Attributes:
        links: 提取的所有链接和图片
        headers: 提取的所有标题
        code_blocks: 提取的所有代码块
        raw_content: 原始 Markdown 内容
    """
    links: list[Link] = field(default_factory=list)
    headers: list[Header] = field(default_factory=list)
    code_blocks: list[CodeBlock] = field(default_factory=list)
    raw_content: str = ""


def generate_header_id(text: str) -> str:
    """
    生成 GitHub 风格的 Header ID
    
    规则：
    1. 转换为小写
    2. 移除非字母数字字符（保留空格和连字符）
    3. 空格转换为连字符
    4. 移除连续的连字符
    
    Args:
        text: 标题文本
    
    Returns:
        GitHub 风格的 Header ID
    """
    # 转换为小写
    result = text.lower()
    
    # 移除非字母数字字符（保留空格、连字符和中文字符）
    result = re.sub(r'[^\w\s\-\u4e00-\u9fff]', '', result)
    
    # 空格转换为连字符
    result = re.sub(r'\s+', '-', result)
    
    # 移除连续的连字符
    result = re.sub(r'-+', '-', result)
    
    # 移除首尾连字符
    result = result.strip('-')
    
    return result


def parse_markdown(content: str) -> ParsedMarkdown:
    """
    解析 Markdown 内容
    
    将 Markdown 内容解析为结构化的 ParsedMarkdown 对象，
    提取链接、标题和代码块。
    
    Args:
        content: Markdown 内容
    
    Returns:
        ParsedMarkdown 对象
    """
    md = MarkdownIt()
    tokens = md.parse(content)
    
    links: list[Link] = []
    headers: list[Header] = []
    code_blocks: list[CodeBlock] = []
    
    i = 0
    while i < len(tokens):
        token = tokens[i]
        
        # 提取标题
        if token.type == 'heading_open':
            level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc.
            line_num = token.map[0] + 1 if token.map else 1
            
            # 下一个 token 是 inline，包含标题文本
            if i + 1 < len(tokens) and tokens[i + 1].type == 'inline':
                header_text = tokens[i + 1].content or ""
                header_id = generate_header_id(header_text)
                headers.append(Header(
                    level=level,
                    text=header_text,
                    id=header_id,
                    line_number=line_num,
                ))
        
        # 提取代码块
        elif token.type == 'fence':
            language = token.info.strip() if token.info else None
            line_num = token.map[0] + 1 if token.map else 1
            code_blocks.append(CodeBlock(
                language=language,
                content=token.content,
                line_number=line_num,
            ))
        
        # 提取内联元素（链接、图片）
        elif token.type == 'inline' and token.children:
            line_num = token.map[0] + 1 if token.map else 1
            
            for j, child in enumerate(token.children):
                if child.type == 'image':
                    # 图片: ![alt](path)
                    src = child.attrGet('src') or ""
                    path, anchor = _split_anchor(src)
                    links.append(Link(
                        text=child.content or "",
                        path=path,
                        line_number=line_num,
                        is_image=True,
                        anchor=anchor,
                    ))
                elif child.type == 'link_open':
                    # 链接: [text](path)
                    href = child.attrGet('href') or ""
                    path, anchor = _split_anchor(href)
                    
                    # 获取链接文本
                    link_text = ""
                    if j + 1 < len(token.children):
                        next_child = token.children[j + 1]
                        if next_child.type == 'text':
                            link_text = next_child.content or ""
                    
                    links.append(Link(
                        text=link_text,
                        path=path,
                        line_number=line_num,
                        is_image=False,
                        anchor=anchor,
                    ))
        
        i += 1
    
    return ParsedMarkdown(
        links=links,
        headers=headers,
        code_blocks=code_blocks,
        raw_content=content,
    )


def _split_anchor(path: str) -> tuple[str, Optional[str]]:
    """
    分离路径和锚点
    
    Args:
        path: 可能包含锚点的路径
    
    Returns:
        (路径, 锚点) 元组，锚点可能为 None
    """
    if '#' in path:
        parts = path.split('#', 1)
        return parts[0], parts[1] if len(parts) > 1 else None
    return path, None


def format_link(link: Link) -> str:
    """
    将 Link 格式化为 Markdown 字符串
    
    Args:
        link: Link 对象
    
    Returns:
        Markdown 格式的链接字符串
    """
    path = link.path
    if link.anchor:
        path = f"{path}#{link.anchor}"
    
    if link.is_image:
        return f"![{link.text}]({path})"
    else:
        return f"[{link.text}]({path})"


def format_header(header: Header) -> str:
    """
    将 Header 格式化为 Markdown 字符串
    
    Args:
        header: Header 对象
    
    Returns:
        Markdown 格式的标题字符串
    """
    prefix = '#' * header.level
    return f"{prefix} {header.text}"


def format_code_block(block: CodeBlock) -> str:
    """
    将 CodeBlock 格式化为 Markdown 字符串
    
    Args:
        block: CodeBlock 对象
    
    Returns:
        Markdown 格式的代码块字符串
    """
    lang = block.language or ""
    return f"```{lang}\n{block.content}```"
