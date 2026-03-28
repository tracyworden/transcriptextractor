## AWS Login 
Login to AWS
```bash
aws sts get-caller-identity --profile AWSAdministratorAccess-792604067869
aws configure list-profiles
aws sso login --profile AWSAdministratorAccess-792604067869
$env:AWS_PROFILE = "AWSAdministratorAccess-792604067869"
or 
Set-AWSCredential -ProfileName "AWSAdministratorAccess-792604067869"   

# Verify
$env:AWS_PROFILE
aws sts get-caller-identity
#If you have multiple profiles you can check the profile in use with 
Get-STSCallerIdentity
```

start venv .\venv\Scripts\Activate.ps1

# Dual storage with Whisper fallback
python extract_transcripts.py --s3-bucket dev-machiningcloud-chatbot-kb --s3-prefix transcripts/ --output-dir ./transcripts --use-whisper-fallback  --aws-profile AWSAdministratorAccess-792604067869

# no-local-save woth whisper fallback
python extract_transcripts.py --s3-bucket dev-machiningcloud-chatbot-kb --s3-prefix transcripts/ --no-local-save --use-whisper-fallback  --aws-profile AWSAdministratorAccess-792604067869