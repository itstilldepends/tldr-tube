# Export Feature - Example Output

This file shows what an exported Markdown summary looks like.

---

## Example: Single Video Export (English)

```markdown
# The Complete Guide to Python Decorators

**Video URL**: https://www.youtube.com/watch?v=example123

## 📊 Metadata

- **Channel**: Python Programming
- **Duration**: 45:23
- **Upload Date**: 2024-01-15
- **Type**: tutorial
- **Transcript Source**: youtube_api
- **Processed Date**: 2024-02-19 12:34:56
- **Tags**: `python`, `decorators`, `programming`, `tutorial`, `advanced`

## 📝 TL;DR

This video provides a comprehensive introduction to Python decorators. It covers the basics of function decorators, class decorators, and advanced topics like decorator chaining and parameterized decorators. The tutorial includes practical examples showing how decorators can be used for logging, timing, caching, and access control. Perfect for intermediate Python developers looking to level up their skills.

## 🕒 Timeline

### [00:00](https://www.youtube.com/watch?v=example123&t=0s) - to 05:23

Introduction to decorators and why they're useful in Python. Covers the basic syntax and the @ symbol notation. Explains that decorators are just functions that take another function as input and return a modified version.

### [05:23](https://www.youtube.com/watch?v=example123&t=323s) - to 12:45

Creating your first decorator - a simple logging decorator that prints when a function is called. Demonstrates the wrapper function pattern and the importance of preserving function metadata using functools.wraps.

### [12:45](https://www.youtube.com/watch?v=example123&t=765s) - to 20:15

Practical example: Building a timing decorator to measure function execution time. Shows how to use time.time() and discusses when this pattern is useful in real-world applications for performance monitoring.

### [20:15](https://www.youtube.com/watch?v=example123&t=1215s) - to 28:30

Advanced topic: Decorators with parameters. Explains the three-level nested function pattern needed to create decorators that accept arguments. Example shows building a retry decorator with configurable retry count.

### [28:30](https://www.youtube.com/watch?v=example123&t=1710s) - to 35:00

Class decorators and the @staticmethod, @classmethod, @property built-in decorators. Explains when to use each and how they modify class methods.

### [35:00](https://www.youtube.com/watch?v=example123&t=2100s) - to 42:10

Decorator chaining - applying multiple decorators to the same function. Discusses the order of execution and potential pitfalls to avoid.

### [42:10](https://www.youtube.com/watch?v=example123&t=2530s) - to 45:23

Real-world use cases: authentication decorators for Flask/FastAPI, caching decorators like functools.lru_cache, and memoization patterns. Concludes with best practices and common mistakes to avoid.

---

*Exported from tldr-tube on 2024-02-19 12:35:00*
```

---

## Example: Single Video Export (Chinese)

```markdown
# Python 装饰器完全指南

**Video URL**: https://www.youtube.com/watch?v=example123

## 📊 元数据

- **频道**: Python Programming
- **时长**: 45:23
- **上传日期**: 2024-01-15
- **类型**: tutorial
- **转录来源**: youtube_api
- **处理日期**: 2024-02-19 12:34:56
- **标签**: `python`, `decorators`, `programming`, `tutorial`, `advanced`

## 📝 概要

本视频全面介绍了 Python 装饰器。内容涵盖函数装饰器、类装饰器的基础知识，以及装饰器链和参数化装饰器等高级主题。教程包含实用示例，展示如何使用装饰器实现日志记录、计时、缓存和访问控制。适合希望提升技能的中级 Python 开发者。

## 🕒 时间线

### [00:00](https://www.youtube.com/watch?v=example123&t=0s) - 至 05:23

介绍装饰器及其在 Python 中的用途。讲解基本语法和 @ 符号表示法。说明装饰器本质上是接受另一个函数作为输入并返回修改版本的函数。

### [05:23](https://www.youtube.com/watch?v=example123&t=323s) - 至 12:45

创建第一个装饰器 - 一个简单的日志装饰器，在函数被调用时打印信息。演示包装函数模式，以及使用 functools.wraps 保留函数元数据的重要性。

...（更多时间线段落）

---

*Exported from tldr-tube on 2024-02-19 12:35:00*
```

---

## Features

### ✅ Included in Export

- **Video metadata**: Title, channel, duration, upload date, tags
- **Processing info**: Transcript source, processed date, video type
- **TL;DR**: Overall summary of the video
- **Timestamped segments**: Each segment with start/end times
- **Clickable links**: Timestamp links that jump directly to YouTube moments
- **Bilingual support**: Separate English and Chinese exports

### 📝 Use Cases

1. **Note-taking**: Save summaries for future reference
2. **Sharing**: Send summaries to friends/colleagues
3. **Integration**: Import into Notion, Obsidian, Roam Research
4. **Offline access**: Keep summaries without database dependency
5. **Course documentation**: Export lecture series for study materials

### 💡 Tips

- Markdown files are plain text and work everywhere
- Use `Ctrl/Cmd + F` to search within exported files
- Combine multiple exports into a single study guide
- Convert to PDF using Pandoc: `pandoc summary.md -o summary.pdf`
- Open in any text editor or note-taking app

---

## Future Enhancements

- [ ] PDF export (formatted, ready to print)
- [ ] Collection export (all videos in a collection as one file)
- [ ] Custom export templates
- [ ] Export with embedded video thumbnails
- [ ] Export to Notion/Obsidian format directly
