from watchdog.observers import Observer
from watchdog.events import *
import time
import os


def auto_push(change):
    os.chdir('./arxivPaperPage/')
    os.system('git add .')
    os.system('git commit -m\"auto' + change + '\"')
    os.system('git push origin gh-pages')


class FileEventHandler(FileSystemEventHandler):
    def __init__(self):
        FileSystemEventHandler.__init__(self)

    def on_moved(self, event):
        if not event.is_directory:
            auto_push(f"file move from {event.src_path} to {event.dest_path}")

    def on_created(self, event):
        if not event.is_directory:
            auto_push(f"create file {event.src_path}")

    def on_deleted(self, event):
        if not event.is_directory:
            auto_push(f"delete file {event.src_path}")

    def on_modified(self, event):
        if not event.is_directory:
            auto_push(f"modify file {event.src_path}")


if __name__ == "__main__":
    observer = Observer()
    event_handler = FileEventHandler()
    dest_dir = './arxivPaperPage/_posts/'
    observer.schedule(event_handler, dest_dir, True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

