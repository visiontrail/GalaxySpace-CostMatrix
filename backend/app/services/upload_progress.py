"""
Upload progress manager
Tracks upload progress for real-time updates
"""
import time
from typing import Dict, Any, Optional
from threading import Lock
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger("upload_progress")


class UploadProgressManager:
    """Manages upload progress tracking"""
    
    def __init__(self):
        self._progress: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def create_task(self, task_id: str, file_name: str) -> None:
        """Create a new upload progress tracking task"""
        with self._lock:
            self._progress[task_id] = {
                "task_id": task_id,
                "file_name": file_name,
                "status": "uploading",
                "progress": 0,
                "current_step": "正在上传文件...",
                "steps": [],
                "error": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
    
    def update_progress(
        self,
        task_id: str,
        progress: int,
        current_step: str,
        status: Optional[str] = None
    ) -> None:
        """Update progress for a task"""
        with self._lock:
            if task_id not in self._progress:
                return
            
            self._progress[task_id]["progress"] = progress
            self._progress[task_id]["current_step"] = current_step
            self._progress[task_id]["updated_at"] = datetime.now().isoformat()
            
            if status:
                self._progress[task_id]["status"] = status
    
    def add_step(self, task_id: str, step: str) -> None:
        """Add a completed step to the task"""
        with self._lock:
            if task_id not in self._progress:
                return
            
            self._progress[task_id]["steps"].append({
                "step": step,
                "completed_at": datetime.now().isoformat()
            })
    
    def complete_task(self, task_id: str, result: Optional[Dict[str, Any]] = None) -> None:
        """Mark task as completed"""
        with self._lock:
            if task_id not in self._progress:
                return
            
            self._progress[task_id]["status"] = "completed"
            self._progress[task_id]["progress"] = 100
            self._progress[task_id]["current_step"] = "上传并解析完成"
            self._progress[task_id]["updated_at"] = datetime.now().isoformat()
            
            if result:
                self._progress[task_id]["result"] = result
    
    def fail_task(self, task_id: str, error: str) -> None:
        """Mark task as failed"""
        with self._lock:
            if task_id not in self._progress:
                return
            
            self._progress[task_id]["status"] = "failed"
            self._progress[task_id]["error"] = error
            self._progress[task_id]["current_step"] = f"上传失败: {error}"
            self._progress[task_id]["updated_at"] = datetime.now().isoformat()
    
    def get_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get progress for a task"""
        with self._lock:
            return self._progress.get(task_id)
    
    def cleanup_task(self, task_id: str) -> None:
        """Remove a task from tracking"""
        with self._lock:
            if task_id in self._progress:
                del self._progress[task_id]
    
    def cleanup_old_tasks(self, max_age_hours: int = 24) -> None:
        """Remove tasks older than max_age_hours"""
        with self._lock:
            now = datetime.now()
            to_remove = []
            
            for task_id, task in self._progress.items():
                created_at = datetime.fromisoformat(task["created_at"])
                age_hours = (now - created_at).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    to_remove.append(task_id)
            
            for task_id in to_remove:
                del self._progress[task_id]
                logger.info(f"Cleaned up old task: {task_id}")


# Global instance
progress_manager = UploadProgressManager()
