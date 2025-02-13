import sys
import os
import subprocess
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QListWidget, QComboBox, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QMessageBox, QProgressBar, QListWidgetItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeDatabase, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent


class DragDropListWidget(QListWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                file_path = url.toLocalFile()
                mime_db = QMimeDatabase()
                mime_type = mime_db.mimeTypeForFile(file_path).name()
                if mime_type.startswith('video/') or file_path.lower().endswith(
                        ('.mp4', '.mov', '.mkv', '.avi', '.webm')):
                    files.append(file_path)

        if files:
            self.parent().add_files(files)
            event.acceptProposedAction()
        else:
            event.ignore()


class VideoConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Lossless Video Converter")
        self.setGeometry(100, 100, 600, 400)
        self.setAcceptDrops(True)
        self.init_ui()
        self.current_converter = None

    def init_ui(self):
        main_layout = QVBoxLayout()
        file_layout = QHBoxLayout()
        controls_layout = QHBoxLayout()

        # File List
        self.file_list = DragDropListWidget()
        file_layout.addWidget(QLabel("Files:"))
        file_layout.addWidget(self.file_list)

        # Add File Button
        self.add_file_button = QPushButton("Add Files")
        self.add_file_button.clicked.connect(self.add_files_dialog)
        controls_layout.addWidget(self.add_file_button)

        # Clear List Button
        self.clear_button = QPushButton("Clear List")
        self.clear_button.clicked.connect(self.file_list.clear)
        controls_layout.addWidget(self.clear_button)

        # Format Dropdown
        self.format_dropdown = QComboBox()
        self.format_dropdown.addItems(['mp4', 'mov', 'mkv', 'avi', 'webm'])
        controls_layout.addWidget(QLabel("Target Format:"))
        controls_layout.addWidget(self.format_dropdown)

        # Start Button
        self.start_button = QPushButton("Start Conversion")
        self.start_button.clicked.connect(self.start_conversion)
        controls_layout.addWidget(self.start_button)

        # Progress Bars
        self.progress_bars = {}
        self.progress_layout = QVBoxLayout()

        main_layout.addLayout(file_layout)
        main_layout.addLayout(controls_layout)
        main_layout.addLayout(self.progress_layout)

        self.setLayout(main_layout)

    def add_files(self, files):
        if not files:
            return

        existing_files = set(self.file_list.item(i).text() for i in range(self.file_list.count()))
        new_files = [f for f in files if f not in existing_files]

        for file in new_files:
            item = QListWidgetItem(file)
            self.file_list.addItem(item)

    def add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Video Files",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*.*)"
        )
        self.add_files(files)

    def start_conversion(self):
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "Warning", "Please add files to convert.")
            return

        target_format = self.format_dropdown.currentText()
        target_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not target_dir:
            return

        # Clear previous progress bars
        for progress_bar in self.progress_bars.values():
            progress_bar.deleteLater()
        self.progress_bars.clear()

        # Disable UI elements
        self.toggle_ui(False)

        # Create new converter instance
        self.current_converter = Converter()

        # Set up files for conversion
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            input_path = item.text()
            file_name = Path(input_path).stem
            output_path = str(Path(target_dir) / f"{file_name}.{target_format}")

            progress_bar = QProgressBar()
            progress_bar.setValue(0)
            progress_bar.setTextVisible(True)
            progress_bar.setFormat(f"%p% - {Path(input_path).name}")
            self.progress_layout.addWidget(progress_bar)
            self.progress_bars[input_path] = progress_bar

            self.current_converter.add_file(input_path, output_path)

        # Connect signals
        self.current_converter.progress_signal.connect(self.update_progress)
        self.current_converter.finished_signal.connect(self.finish_conversion)
        self.current_converter.error_signal.connect(self.error_conversion)
        self.current_converter.all_finished_signal.connect(self.all_conversions_finished)

        # Start conversion
        self.current_converter.start()

    def toggle_ui(self, enabled: bool):
        self.start_button.setEnabled(enabled)
        self.format_dropdown.setEnabled(enabled)
        self.add_file_button.setEnabled(enabled)
        self.clear_button.setEnabled(enabled)
        self.file_list.setEnabled(enabled)

    def update_progress(self, file_path, progress):
        if file_path in self.progress_bars:
            self.progress_bars[file_path].setValue(progress)

    def finish_conversion(self, file_path):
        if file_path in self.progress_bars:
            self.progress_bars[file_path].setValue(100)
            logging.info(f"Conversion finished for {file_path}")

    def error_conversion(self, file_path, error):
        QMessageBox.critical(self, "Error", f"Error processing {file_path}:\n{error}")
        logging.error(f"Error converting {file_path}: {error}")

    def all_conversions_finished(self):
        self.toggle_ui(True)
        QMessageBox.information(self, "Complete", "All conversions finished!")
        logging.info("All conversions completed")


class Converter(QThread):
    progress_signal = pyqtSignal(str, int)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str, str)
    all_finished_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.conversion_queue = []

    def add_file(self, input_path, output_path):
        self.conversion_queue.append((input_path, output_path))

    def run(self):
        for input_path, output_path in self.conversion_queue:
            try:
                logging.info(f"Starting conversion: {input_path} -> {output_path}")
                self.convert(input_path, output_path)
                self.finished_signal.emit(input_path)
            except Exception as e:
                logging.error(f"Conversion error for {input_path}: {str(e)}")
                self.error_signal.emit(input_path, str(e))

        self.all_finished_signal.emit()

    def convert(self, input_path, output_path):
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except FileNotFoundError:
            raise Exception("ffmpeg is not installed or not found in system PATH")
        except subprocess.CalledProcessError:
            raise Exception("Error checking ffmpeg version")

        try:
            # Get video duration for progress calculation
            duration = self.get_video_duration(input_path)
            if duration == 0:
                raise Exception("Could not determine video duration")

            # Prepare ffmpeg command
            cmd = [
                'ffmpeg',
                '-y',  # Overwrite output file if it exists
                '-i', input_path,
                '-c', 'copy',  # Copy streams without re-encoding
                output_path
            ]

            # Start conversion process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # Monitor conversion progress
            while True:
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                if 'time=' in line:
                    current_time = self.parse_time(line)
                    if current_time > 0:
                        progress = min(int((current_time / duration) * 100), 100)
                        self.progress_signal.emit(input_path, progress)

            # Check if conversion was successful
            if process.returncode != 0:
                error_output = process.stderr.read()
                raise Exception(f"FFmpeg error (code {process.returncode}): {error_output}")

        except Exception as e:
            raise Exception(f"Conversion failed: {str(e)}")

    def get_video_duration(self, input_path):
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                input_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except Exception as e:
            logging.error(f"Error getting video duration: {str(e)}")
            return 0

    def parse_time(self, line):
        try:
            time_str = line.split('time=')[1].split()[0]
            hours, minutes, seconds = map(float, time_str.split(':'))
            return hours * 3600 + minutes * 60 + seconds
        except:
            return 0


if __name__ == '__main__':
    logging.basicConfig(
        filename='video_converter.log',
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    app = QApplication(sys.argv)
    converter = VideoConverter()
    converter.show()
    sys.exit(app.exec())