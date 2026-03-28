# Deployment Guide

## EC2 Instance Setup for Video Transcription

### 1. Launch EC2 Instance

- AMI: Amazon Linux 2023 (or Ubuntu 22.04)
- Instance type: `g4dn.xlarge` (T4 GPU, 4 vCPU, 16 GB RAM)
- Region: `us-east-1` (same region as `s3://mw-family-videos-1/`)
- Storage: 100 GB gp3 (enough for temp files during processing)
- IAM Role: Attach a role with S3 read/write access to `mw-family-videos-1`

Example IAM policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws:s3:::mw-family-videos-1",
        "arn:aws:s3:::mw-family-videos-1/*"
      ]
    }
  ]
}
```

### 2. Install System Dependencies

```bash
# Update packages
sudo yum update -y          # Amazon Linux
# sudo apt update && sudo apt upgrade -y  # Ubuntu

# Install Python 3.13 (if not available, use 3.11+)
sudo yum install -y python3.11 python3.11-pip python3.11-devel

# Install ffmpeg and ffprobe
sudo yum install -y ffmpeg   # Amazon Linux
# sudo apt install -y ffmpeg  # Ubuntu

# If ffmpeg not in default repos (Amazon Linux):
# sudo yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-2023.noarch.rpm
# sudo yum install -y ffmpeg

# Install git
sudo yum install -y git

# Install NVIDIA drivers (for GPU — g4dn instances)
# Amazon Linux 2023 with DLAMI may already have these
nvidia-smi  # Check if drivers are already installed
```

### 3. Clone Repo and Set Up Python Environment

```bash
git clone <your-repo-url> ~/TranscriptExtractor
cd ~/TranscriptExtractor

python3 -m venv venv
source venv/bin/activate
```

### 4. Install Python Dependencies (GPU-enabled)

The `requirements.txt` has CPU torch by default. For GPU transcription, install CUDA torch first, then the rest:

```bash
# Install CUDA-enabled PyTorch FIRST
pip install torch --index-url https://download.pytorch.org/whl/cu121

# Then install everything else (torch will be skipped since it's already installed)
pip install -r requirements.txt

# Verify GPU is available
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
# Should print: CUDA available: True
```

### 5. Verify Setup

```bash
# Check ffmpeg
ffmpeg -version

# Check ffprobe
ffprobe -version

# Check whisper can load
python -c "import whisper; m = whisper.load_model('base'); print('Whisper OK')"

# Check S3 access (no --aws-profile needed with IAM role)
python -c "import boto3; s3 = boto3.client('s3'); print(len(s3.list_objects_v2(Bucket='mw-family-videos-1', MaxKeys=1)['Contents']), 'objects')"
```

### 6. Run Transcription

```bash
# Dry run first
python s3_video_transcribe.py --dry-run --verbose

# Small test batch
python s3_video_transcribe.py --limit 10 --verbose

# Full run (no --aws-profile needed with IAM role)
# Use screen or tmux so it survives SSH disconnect
screen -S transcribe
python s3_video_transcribe.py --verbose
# Ctrl+A, D to detach
# screen -r transcribe to reattach
```

### 7. Monitor Progress

```bash
# Check progress from another terminal
cat transcribe_progress.json | python -m json.tool | grep -c "source_key"

# Check errors
cat transcription_errors.log

# Check if still running
screen -ls
```

---

## Local Development Commands

### Video Convert (Step 1 — already completed)

```bash
# Dry run
python s3_video_convert.py --dry-run --verbose --aws-profile austin

# Run with local file review
python s3_video_convert.py --limit 50 --keep-local --verbose --aws-profile austin

# Full run
python s3_video_convert.py --aws-profile austin
```

### Video Transcription (Step 2)

```bash
# Dry run
python s3_video_transcribe.py --dry-run --verbose --aws-profile austin

# Small test batch
python s3_video_transcribe.py --limit 5 --verbose --aws-profile austin

# Full run (local — will be slow without GPU)
python s3_video_transcribe.py --verbose --aws-profile austin
```

### YouTube Transcript Extraction (existing)

```bash
python extract_transcripts.py \
  --s3-bucket dev-machiningcloud-chatbot-kb \
  --s3-prefix transcripts/ \
  --aws-profile austin
```

---

## Cost Estimates

### EC2 g4dn.xlarge
- On-demand: ~$0.526/hr
- Spot: ~$0.16/hr (use spot if you can tolerate interruptions — progress tracker handles resume)
- Estimated runtime: 100-200 hours for 5,621 videos
- Estimated cost: $52-$105 on-demand, $16-$32 spot

### Tips to Reduce Cost
- Use spot instances — the progress tracker makes this safe (resume on interruption)
- Run `--limit` batches and stop the instance between batches if reviewing
- The `base` Whisper model is the fastest; `tiny` is even faster but lower quality
