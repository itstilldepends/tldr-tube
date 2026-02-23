"""
Analyze typical content length in tldr-tube to choose embedding model.

This helps us understand:
1. How long are our titles, TL;DRs?
2. Will we exceed token limits?
3. Should we truncate?
"""

import tiktoken

# Use cl100k_base tokenizer (similar to most modern models)
enc = tiktoken.get_encoding("cl100k_base")

# Simulate typical tldr-tube content
examples = [
    {
        "title": "Python Decorators Tutorial - Complete Guide for Beginners",
        "tldr": "This comprehensive video covers Python decorators from basics to advanced patterns. We start with simple function decorators, then explore class decorators, decorator chaining, and decorators with arguments. Practical examples include logging, timing, caching, and authentication decorators commonly used in web frameworks.",
        "tldr_zh": "本视频全面讲解 Python 装饰器，从基础到高级模式。首先介绍简单的函数装饰器，然后探讨类装饰器、装饰器链和带参数的装饰器。实用示例包括日志记录、计时、缓存和 Web 框架中常用的身份验证装饰器。"
    },
    {
        "title": "React Hooks Deep Dive - useState, useEffect, Custom Hooks",
        "tldr": "Deep dive into React Hooks including useState for state management, useEffect for side effects, and creating custom hooks. We'll build real-world examples and discuss common pitfalls and best practices for using hooks in production applications.",
        "tldr_zh": "深入探讨 React Hooks，包括用于状态管理的 useState、用于副作用的 useEffect 以及创建自定义 Hooks。我们将构建实际示例，讨论在生产应用中使用 Hooks 的常见陷阱和最佳实践。"
    },
    {
        "title": "Machine Learning Fundamentals - Linear Regression Explained",
        "tldr": "Introduction to machine learning focusing on linear regression. Covers mathematical foundations, implementation from scratch in Python, gradient descent optimization, and practical applications. Includes hands-on coding examples and visualization of concepts.",
        "tldr_zh": "机器学习基础：线性回归详解。涵盖数学基础、Python 从头实现、梯度下降优化和实际应用。包含实践编码示例和概念可视化。"
    },
    {
        "title": "短标题",
        "tldr": "This is a very short video summary.",
        "tldr_zh": "这是一个非常简短的视频摘要。"
    },
    {
        "title": "超长标题示例 - 包含很多关键词的标题 - Python JavaScript TypeScript React Vue Angular Node.js Django Flask FastAPI Machine Learning Deep Learning",
        "tldr": "This is an extremely long summary that contains a lot of information about various topics including programming languages, frameworks, libraries, tools, methodologies, best practices, design patterns, algorithms, data structures, and many other technical concepts that developers need to know when building modern web applications and software systems in today's technology landscape.",
        "tldr_zh": "这是一个极长的摘要，包含大量关于各种主题的信息，包括编程语言、框架、库、工具、方法论、最佳实践、设计模式、算法、数据结构以及开发人员在当今技术环境中构建现代 Web 应用程序和软件系统时需要了解的许多其他技术概念。"
    }
]

print("="*80)
print("Content Length Analysis for tldr-tube Embeddings")
print("="*80)
print()

total_tokens = []

for i, ex in enumerate(examples, 1):
    print(f"Example {i}:")
    print(f"Title: {ex['title'][:60]}...")
    print()

    # Tokenize each field
    title_tokens = len(enc.encode(ex["title"]))
    tldr_tokens = len(enc.encode(ex["tldr"]))
    tldr_zh_tokens = len(enc.encode(ex["tldr_zh"]))

    # Combined (what we'll actually embed)
    combined = f"{ex['title']} {ex['tldr']} {ex['tldr_zh']}"
    combined_tokens = len(enc.encode(combined))

    print(f"  Title:     {title_tokens:4d} tokens")
    print(f"  TL;DR EN:  {tldr_tokens:4d} tokens")
    print(f"  TL;DR ZH:  {tldr_zh_tokens:4d} tokens")
    print(f"  ─────────────────────")
    print(f"  COMBINED:  {combined_tokens:4d} tokens")

    total_tokens.append(combined_tokens)

    # Check against model limits
    if combined_tokens <= 128:
        status = "✅ OK for MiniLM (128)"
    elif combined_tokens <= 384:
        status = "✅ OK for mpnet (384)"
    elif combined_tokens <= 512:
        status = "✅ OK for e5-base/LaBSE (512)"
    else:
        status = f"⚠️  EXCEEDS 512 tokens (will be truncated)"

    print(f"  Status:    {status}")
    print()

print("="*80)
print("Summary Statistics")
print("="*80)
print()
print(f"Average tokens:  {sum(total_tokens) / len(total_tokens):.1f}")
print(f"Min tokens:      {min(total_tokens)}")
print(f"Max tokens:      {max(total_tokens)}")
print()

# Model recommendations
print("Model Recommendations:")
print()
print("❌ MiniLM (128 tokens):")
exceeded_minilm = sum(1 for t in total_tokens if t > 128)
print(f"   {exceeded_minilm}/{len(total_tokens)} examples exceed limit")
print(f"   Will truncate {exceeded_minilm/len(total_tokens)*100:.0f}% of content")
print()

print("⚠️  mpnet (384 tokens):")
exceeded_mpnet = sum(1 for t in total_tokens if t > 384)
print(f"   {exceeded_mpnet}/{len(total_tokens)} examples exceed limit")
print(f"   Will truncate {exceeded_mpnet/len(total_tokens)*100:.0f}% of content")
print()

print("✅ e5-base/LaBSE (512 tokens):")
exceeded_e5 = sum(1 for t in total_tokens if t > 512)
print(f"   {exceeded_e5}/{len(total_tokens)} examples exceed limit")
print(f"   Will truncate {exceeded_e5/len(total_tokens)*100:.0f}% of content")
print()

print("="*80)
print("Recommendation for tldr-tube:")
print("="*80)
print()
print("Use: intfloat/multilingual-e5-base (512 tokens)")
print()
print("Reasons:")
print("1. ✅ Fits 80%+ of typical content without truncation")
print("2. ✅ Best quality among local models")
print("3. ✅ Modern architecture (2023)")
print("4. ✅ Excellent Chinese + English support")
print()
print("For edge cases (very long content):")
print("- Automatic truncation is fine (loses tail of summary)")
print("- First 512 tokens contain the most important info anyway")
print()
