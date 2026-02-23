# 导出功能使用指南 / Export Feature Guide

## 🎯 功能概述 / Overview

tldr-tube 现在支持将视频摘要导出为 Markdown 格式，方便保存、分享和集成到笔记应用中。

tldr-tube now supports exporting video summaries to Markdown format for easy saving, sharing, and integration with note-taking apps.

---

## 📥 如何导出 / How to Export

### 单个视频 / Single Video

1. **处理视频** - 在"➕ New Video"页面输入 YouTube URL 并处理
   **Process video** - Enter YouTube URL in "➕ New Video" page and process

2. **查看结果** - 等待处理完成，查看摘要结果
   **View results** - Wait for processing to complete, view summary results

3. **导出** - 在摘要页面，找到"💾 Export Summary"部分
   **Export** - On the summary page, find the "💾 Export Summary" section

4. **选择语言** - 点击以下按钮之一：
   **Choose language** - Click one of the following buttons:
   - `📥 Download English (MD)` - 导出英文版
   - `📥 Download Chinese (MD)` - 导出中文版

5. **保存文件** - 文件将自动下载，命名格式为 `{video_id}_summary_{language}.md`
   **Save file** - File will be downloaded automatically, named as `{video_id}_summary_{language}.md`

---

## 📄 导出内容 / Export Contents

导出的 Markdown 文件包含：
The exported Markdown file includes:

### 1. 视频元数据 / Video Metadata
- 标题 / Title
- 频道名称 / Channel name
- 视频时长 / Duration
- 上传日期 / Upload date
- 标签 / Tags
- 视频类型 / Video type (tutorial/podcast/lecture/other)
- 转录来源 / Transcript source (YouTube API or Whisper)
- 处理日期 / Processing date

### 2. TL;DR 概要 / TL;DR Summary
- 5-7 句话的整体总结 / 5-7 sentence overall summary

### 3. 时间线 / Timeline
- 分段摘要 / Segmented summaries
- 每段的开始和结束时间 / Start and end time for each segment
- **可点击的时间戳链接** / **Clickable timestamp links** - 在 Markdown 阅读器中点击可直接跳转到 YouTube 对应时刻
  Click in Markdown reader to jump directly to YouTube moment

---

## 💡 使用场景 / Use Cases

### 📚 笔记整理 / Note Taking
将导出的 Markdown 文件导入到：
Import exported Markdown files into:
- **Notion** - 直接粘贴或导入 / Paste directly or import
- **Obsidian** - 放入 vault 文件夹 / Place in vault folder
- **Roam Research** - 导入为页面 / Import as page
- **Bear / Typora / iA Writer** - 任何 Markdown 编辑器 / Any Markdown editor

### 🤝 分享摘要 / Share Summaries
- 发送给同事或朋友 / Send to colleagues or friends
- 在 GitHub 上作为学习资料 / As learning materials on GitHub
- 发布到博客 / Publish to blog

### 🎓 课程笔记 / Course Notes
- 观看在线课程时导出每节课的摘要 / Export summary for each lesson while watching online courses
- 合并多个导出文件创建完整的课程笔记 / Combine multiple exports to create complete course notes

### 📖 离线阅读 / Offline Reading
- 在没有网络的情况下查看摘要 / View summaries without internet connection
- 不依赖数据库，纯文本存档 / Pure text archive, no database dependency

---

## 🔧 高级用法 / Advanced Usage

### 转换为 PDF / Convert to PDF
使用 Pandoc 将 Markdown 转换为 PDF：
Use Pandoc to convert Markdown to PDF:

```bash
# 安装 Pandoc / Install Pandoc
brew install pandoc  # macOS
sudo apt install pandoc  # Linux

# 转换 / Convert
pandoc video_summary_en.md -o video_summary.pdf

# 使用自定义样式 / With custom styling
pandoc video_summary_en.md -o video_summary.pdf --pdf-engine=xelatex -V mainfont="PingFang SC"
```

### 合并多个摘要 / Combine Multiple Summaries
使用命令行合并多个导出文件：
Use command line to combine multiple export files:

```bash
cat lecture1_summary_en.md lecture2_summary_en.md lecture3_summary_en.md > full_course.md
```

### 搜索摘要 / Search Within Summaries
在 Markdown 文件中搜索关键词：
Search for keywords in Markdown files:

```bash
# 在当前目录的所有 .md 文件中搜索 / Search in all .md files
grep -r "keyword" *.md

# 使用 ripgrep (更快) / Use ripgrep (faster)
rg "keyword" *.md
```

---

## ⚙️ 技术细节 / Technical Details

### 文件格式 / File Format
- **格式** / **Format**: Markdown (.md)
- **编码** / **Encoding**: UTF-8
- **换行** / **Line Endings**: Unix (LF)
- **命名** / **Naming**: `{video_id}_summary_{en|zh}.md`

### 链接格式 / Link Format
时间戳链接格式：
Timestamp link format:
```markdown
[00:00](https://www.youtube.com/watch?v={video_id}&t={seconds}s)
```

### 元数据 / Metadata
导出文件底部包含导出时间戳：
Export file footer includes export timestamp:
```markdown
*Exported from tldr-tube on 2024-02-19 12:35:00*
```

---

## 🚀 未来功能 / Future Features

### 即将推出 / Coming Soon
- [ ] **PDF 导出** / **PDF Export** - 直接导出为格式化的 PDF 文件
  Directly export as formatted PDF file

- [ ] **Collection 导出** / **Collection Export** - 将整个 Collection 的所有视频导出为单个文件
  Export all videos in a Collection as a single file

- [ ] **自定义模板** / **Custom Templates** - 允许用户自定义导出格式
  Allow users to customize export format

- [ ] **嵌入缩略图** / **Embedded Thumbnails** - 在导出文件中包含视频缩略图
  Include video thumbnails in exported files

- [ ] **直接集成** / **Direct Integration** - 直接导出到 Notion/Obsidian API
  Direct export to Notion/Obsidian API

---

## ❓ 常见问题 / FAQ

### Q: 导出文件可以编辑吗？
### Q: Can I edit exported files?
**A:** 可以！导出的 Markdown 文件是纯文本格式，可以用任何文本编辑器编辑。
**A:** Yes! Exported Markdown files are plain text and can be edited with any text editor.

### Q: 导出的时间戳链接在哪里可以点击？
### Q: Where can I click timestamp links?
**A:** 在支持 Markdown 的应用中（Notion, Obsidian, GitHub, VS Code 等），时间戳会显示为可点击的链接。
**A:** In Markdown-supporting apps (Notion, Obsidian, GitHub, VS Code, etc.), timestamps will appear as clickable links.

### Q: 可以同时导出中英文吗？
### Q: Can I export both English and Chinese at once?
**A:** 目前需要分别点击两个按钮。未来版本可能会添加"导出双语版本"功能。
**A:** Currently, you need to click two buttons separately. Future versions may add "Export Bilingual" feature.

### Q: PDF 导出什么时候可用？
### Q: When will PDF export be available?
**A:** PDF 导出功能在开发计划中。目前可以使用 Pandoc 将 Markdown 转换为 PDF（见上方"高级用法"）。
**A:** PDF export is in the development plan. Currently, you can use Pandoc to convert Markdown to PDF (see "Advanced Usage" above).

---

## 🐛 问题反馈 / Report Issues

如果导出功能遇到问题，请：
If you encounter issues with export functionality:

1. 检查浏览器控制台是否有错误 / Check browser console for errors
2. 确认视频已完整处理 / Confirm video is fully processed
3. 在 GitHub Issues 报告问题 / Report issue on GitHub Issues

---

**Made with ❤️ for efficient learning**
