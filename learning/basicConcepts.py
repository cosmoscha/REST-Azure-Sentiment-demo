from fastapi import BackgroundTasks, FastAPI
from typing import Optional
from pydantic import BaseModel

app = FastAPI()

@app.get("/")
def root():
  return {"message": "Hello World"}

@app.get("/courses/{course_name}")
def read_course(course_name):
    return {"course_name": course_name}

@app.get("/courses/{course_id}")
def read_course(course_id: int):
    return {"course_id": course_id}

course_items = [{"course_name": "Python"}, {"course_name": "NodeJS"}, {"course_name": "Machine Learning"}]

@app.get("/courses/")
def read_courses(start: int, end: int):
    return course_items[start : start + end]

@app.get("/courses0/")
def read_courses(start: int = 0, end: int = 10):
    return course_items[start : start + end]

@app.get("/courses/{course_id}")
def read_courses(course_id: int, q: Optional[str] = None):
    if q is not None:
        return {"course_name": course_items[course_id], "q": q}
    return {"course_name": course_items[course_id]}


class Course(BaseModel):
  name: str
  description: Optional[str] = None
  price: int
  author: Optional[str] = None

@app.post("/courses/")
def create_course(course: Course):
  return course

def write_notification(email: str, message=""):
  with open("log.txt", mode="w") as email_file:
    content = f"notification for {email}: {message}"
    email_file.write(content)

@app.post("/send-notification/{email}")
def send_notification(email: str, background_tasks: BackgroundTasks):
  background_tasks.add_task(write_notification, email, message="some notification")
  return {"message": "Notification sent in the background"}
