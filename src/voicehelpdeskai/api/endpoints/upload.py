"""File upload API endpoints."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List

router = APIRouter()


class UploadResponse(BaseModel):
    """Upload response model."""
    message: str
    filename: str
    file_size: int
    content_type: str


@router.post("/audio", response_model=UploadResponse)
async def upload_audio_file(file: UploadFile = File(...)):
    """Upload an audio file."""
    # Validate file type
    if not file.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=400,
            detail="File must be an audio file"
        )
    
    # Read file content (in a real implementation, you'd save this)
    content = await file.read()
    file_size = len(content)
    
    # TODO: Implement actual file saving and processing
    # For now, just return success response
    
    return UploadResponse(
        message="Audio file uploaded successfully",
        filename=file.filename,
        file_size=file_size,
        content_type=file.content_type,
    )


@router.post("/batch", response_model=List[UploadResponse])
async def upload_multiple_files(files: List[UploadFile] = File(...)):
    """Upload multiple files."""
    responses = []
    
    for file in files:
        if not file.content_type.startswith("audio/"):
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} must be an audio file"
            )
        
        content = await file.read()
        file_size = len(content)
        
        responses.append(UploadResponse(
            message="Audio file uploaded successfully",
            filename=file.filename,
            file_size=file_size,
            content_type=file.content_type,
        ))
    
    return responses