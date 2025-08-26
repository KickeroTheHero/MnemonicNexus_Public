#!/usr/bin/env python3
"""
Pin Docker image digests for security
Fetches current digests for images and updates Dockerfiles
"""

import subprocess
import re
from typing import Dict, Optional

def get_image_digest(image: str) -> Optional[str]:
    """Get the current digest for a Docker image"""
    try:
        # Pull the image to ensure we have the latest
        print(f"📥 Pulling {image}...")
        subprocess.run(["docker", "pull", image], 
                      capture_output=True, check=True)
        
        # Get the digest
        result = subprocess.run(
            ["docker", "inspect", "--format={{index .RepoDigests 0}}", image],
            capture_output=True, text=True, check=True
        )
        
        repo_digest = result.stdout.strip()
        if "@sha256:" in repo_digest:
            # Extract just the digest part
            digest = repo_digest.split("@sha256:")[1]
            return f"sha256:{digest}"
        
        return None
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get digest for {image}: {e}")
        return None

def update_dockerfile(filepath: str, image: str, digest: str) -> bool:
    """Update Dockerfile with pinned digest"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Pattern to match FROM lines with the image
        pattern = rf'FROM\s+{re.escape(image)}(?::[^@\s]+)?(?:@sha256:[a-f0-9]+)?'
        replacement = f'FROM {image}@{digest}'
        
        new_content = re.sub(pattern, replacement, content)
        
        if new_content != content:
            with open(filepath, 'w') as f:
                f.write(new_content)
            print(f"✅ Updated {filepath} with {image}@{digest[:12]}...")
            return True
        else:
            print(f"⚠️  No changes needed for {filepath}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to update {filepath}: {e}")
        return False

def main():
    """Main function to pin image digests"""
    print("🔒 Pinning Docker image digests for security...")
    
    # Images to pin with their Dockerfile locations
    images_to_pin = [
        {
            "image": "python:3.11-slim",
            "dockerfile": "services/gateway/Dockerfile"
        },
        {
            "image": "pgvector/pgvector:pg16", 
            "dockerfile": "infra/postgres-age/Dockerfile"
        }
    ]
    
    updated_count = 0
    
    for item in images_to_pin:
        image = item["image"]
        dockerfile = item["dockerfile"]
        
        print(f"\n🔍 Processing {image}...")
        
        # Get current digest
        digest = get_image_digest(image)
        if not digest:
            print(f"❌ Could not get digest for {image}")
            continue
        
        # Update Dockerfile
        if update_dockerfile(dockerfile, image.split(':')[0], digest):
            updated_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Images processed: {len(images_to_pin)}")
    print(f"   Dockerfiles updated: {updated_count}")
    
    if updated_count > 0:
        print("\n💡 Next steps:")
        print("   1. Review the updated Dockerfiles")
        print("   2. Test image builds with pinned digests")
        print("   3. Commit the changes")
        print("   4. Set up digest update process for future releases")
    else:
        print("\n✅ All Dockerfiles are already up to date")

if __name__ == "__main__":
    main()
