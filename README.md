# IntelliSubs - Smart Subtitle Toolkit

本项目提供了一个自动化的字幕处理流程，包括音频转录、字幕规范化、字幕翻译以及将字幕嵌入视频文件。

## 功能特性

- **音频转录**：使用 OpenAI Whisper 模型将音频或视频中的语音转录为 SRT 字幕文件。
    - 支持多种 Whisper 模型大小 (`tiny`, `base`, `small`, `medium`, `large`, `turbo`) 以平衡速度和准确性。
    - 自动检测CUDA环境以使用GPU加速。
- **字幕规范化**：
    - **分割长句**：在句子中的标点符号处（如 . , ? ! ; : 。 ， ？ ！ ； ： 、）分割长字幕行，并按字符数比例分配时间戳。
    - **合并短句**：确保每条字幕都以标点符号结束。
    - **优化短句合并**：特别针对以逗号(,)、中文逗号(，)或顿号(、)结尾的短句进行合并，同时确保合并后的句子不超过10个单词，以提高可读性。
- **字幕翻译**：
    - 支持多种翻译引擎（当前支持 Google Gemini 和 智谱 AI）。
    - 批量翻译字幕，保持SRT格式。
    - 智能分批处理，提高翻译效率和上下文连贯性。
- **字幕嵌入**：
    - 使用 `ffmpeg` 将处理好的SRT字幕文件嵌入到视频文件中。
    - 自动复制视频和音频流，仅添加字幕轨道。
    - 可自定义嵌入字幕的标题。
- **一体化流程**：通过 `main.py` 脚本，可以一键完成从原始音/视频到带翻译字幕视频的完整流程。
- **灵活配置**：
    - 支持命令行参数配置各个处理步骤。
    - 可以跳过任意步骤（例如，直接从已有的SRT文件开始规范化或翻译）。
    - 可指定源语言和目标语言。
    - 中间处理结果会保存在 `temp` 目录下，方便查阅。

## 项目结构

```
Translator/
├── main.py             # 主程序入口，整合所有流程
├── transcribe.py       # 音频转录模块
├── normalize.py        # 字幕规范化模块
├── translator.py       # 字幕翻译模块
├── .env.example        # 环境变量示例文件
└── README.md           # 项目说明文件
```

## 安装与配置

1.  **克隆项目**：
    ```bash
    git clone <your-repository-url>
    cd Translator
    ```

2.  **安装依赖**：
    建议使用虚拟环境。
    ```bash
    python -m venv venv
    source venv/bin/activate  # macOS/Linux
    # venv\Scripts\activate  # Windows
    ```
    安装所需的 Python 包：
    ```bash
    pip install openai-whisper pydub torch torchvision torchaudio google-generativeai zhipuai python-dotenv
    ```
    **注意**：`torch` 的安装可能需要根据您的 CUDA 版本进行特定配置以启用 GPU 支持。请参考 [PyTorch 官方网站](https://pytorch.org/) 获取详细安装指南。

3.  **安装 FFmpeg**：
    字幕嵌入功能依赖 `ffmpeg`。请确保您的系统中已安装 `ffmpeg` 并将其添加到了系统路径。
    -   **macOS (使用 Homebrew)**: `brew install ffmpeg`
    -   **Linux (使用 apt)**: `sudo apt update && sudo apt install ffmpeg`
    -   **Windows**: 从 [FFmpeg 官网](https://ffmpeg.org/download.html) 下载并手动配置环境变量。

4.  **配置 API 密钥**：
    翻译功能需要相应的 API 密钥。
    -   复制 `.env.example` 文件为 `.env`：
        ```bash
        cp .env.example .env
        ```
    -   编辑 `.env` 文件，填入您的 API 密钥：
        ```
        # .env
        GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
        ZHIPU_API_KEY="YOUR_ZHIPU_API_KEY"
        ```

## 使用方法

核心脚本是 `main.py`，它提供了命令行接口来控制整个处理流程。

### 基本用法

```bash
python main.py <input_audio_or_video_file> [options]
```

### 示例

1.  **完整流程（音频转录 -> 规范化 -> 翻译为中文 -> 嵌入字幕到视频）**：
    假设输入文件是 `my_video.mp4`。
    ```bash
    python main.py my_video.mp4 --embed-subtitle
    ```
    -   转录的英文字幕会保存在 `temp/my_video_transcribed.srt`。
    -   规范化后的英文字幕会保存在 `temp/my_video_normalized.srt`。
    -   翻译后的中文字幕会保存在 `my_video_zh.srt`。
    -   嵌入字幕后的视频会保存在 `my_video_zh_subtitled.mp4`。

2.  **指定 Whisper 模型和翻译引擎**：
    ```bash
    python main.py my_audio.mp3 -m medium -a gemini
    ```
    这将使用 `medium` 大小的 Whisper 模型进行转录，并使用 `gemini` 进行翻译。

3.  **从现有 SRT 文件开始翻译和嵌入**：
    ```bash
    python main.py existing_subtitle.srt --skip-transcribe --skip-normalize --video-file my_video.mp4 --embed-subtitle
    ```

4.  **仅转录和规范化，不翻译**：
    目标语言设置为源语言即可跳过翻译。
    ```bash
    python main.py my_audio.mp3 -sl en -tl en
    ```
    最终会得到规范化后的英文字幕 `my_audio_en.srt`。

5.  **指定输出文件名和字幕标题**：
    ```bash
    python main.py my_video.mkv -o final_subs.srt --embed-subtitle --output-video final_video.mkv --subtitle-title "Chinese Subs"
    ```

### 命令行参数 (`main.py`)

-   `input_file`: （必须）输入的音频或视频文件路径。
-   `-o, --output`: 输出的最终字幕文件路径（可选，默认基于输入文件名生成）。
-   `-sl, --source-language`: 翻译前的源语言 (`zh` 或 `en`，默认 `en`)。
-   `-tl, --target-language`: 翻译后的目标语言 (`zh` 或 `en`，默认 `zh`)。
-   `-m, --model`: Whisper 模型大小 (`tiny`, `base`, `small`, `medium`, `turbo`, `large`，默认 `turbo`)。
-   `-a, --agent`: 翻译代理/引擎 (`gemini` 或 `zhipu`，默认 `zhipu`)。
-   `--skip-transcribe`: 跳过转录步骤。
-   `--skip-normalize`: 跳过规范化步骤。
-   `--intermediate-dir`: 中间文件保存目录 (默认 `temp`)。
-   `--embed-subtitle`: 将生成的字幕嵌入到视频文件中。
-   `--video-file`: 用于嵌入字幕的视频文件路径（如果与 `input_file` 相同，可不提供）。
-   `--output-video`: 嵌入字幕后的输出视频文件路径（可选，默认基于视频文件名生成）。
-   `--subtitle-title`: 嵌入字幕的标题 (默认 `chs`，如果目标语言为中文，则为 `中文字幕`)。

### 单独使用模块

您也可以单独运行 `transcribe.py`、`normalize.py` 或 `translator.py` 来执行特定任务。它们各自也支持命令行参数。

例如，仅规范化一个 SRT 文件：
```bash
python normalize.py input.srt -o normalized_output.srt
```

## 注意事项

-   **处理时间**：音频转录（尤其是使用大型模型或CPU处理时）和批量翻译可能需要较长时间。
-   **API 配额**：使用在线翻译服务时，请注意您的 API 调用频率和配额限制。
-   **FFmpeg 依赖**：确保 `ffmpeg` 正确安装并配置在系统路径中，否则字幕嵌入会失败。
-   **文件编码**：所有SRT文件均使用 UTF-8 编码。

## 未来可能的改进

-   支持更多翻译引擎。
-   支持更多字幕格式（如 ASS）。
-   提供更详细的进度反馈。
-   GUI 界面。

欢迎提交 Pull Requests 或 Issues 来改进此项目。