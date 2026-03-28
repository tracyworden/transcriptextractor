## To convert videos and move from S3 archive to S3 new

## test
```bash
python s3_video_convert.py --dry-run --verbose --aws-profile austin
```

## run and keep files local, limit the amount of files to proocess and display details to stndout
```bash
python s3_video_convert.py --limit 50 --keep-local --verbose --aws-profile austin
```

## run all and delete local files as you go 
```bash
python s3_video_convert.py --aws-profile <your-profile>
```

## Create transcripts
### With S3 Upload
```bash
python extract_transcripts.py \
  --s3-bucket dev-machiningcloud-chatbot-kb \
  --s3-prefix transcripts/ \
  --aws-profile your-profile
```