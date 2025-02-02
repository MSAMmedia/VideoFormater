import sys
import os
import subprocess
import logging
import json
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QListWidget, QComboBox, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QMessageBox, QProgressBar, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QCheckBox, QGroupBox, QHeaderView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeDatabase, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent


class VideoMetadata:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.filename = Path(filepath).name
        self.filesize = os.path.getsize(filepath)
        self.duration = 0
        self.video_codec = ""
        self.audio_codec = ""
        self.resolution = ""
        self.bitrate = ""
        self.fetch_metadata()

    def fetch_metadata(self):
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                self.filepath
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)

            # Get format information
            format_data = data.get('format', {})
            self.duration = float(format_data.get('duration', 0))
            self.bitrate = format_data.get('bit_rate', 'N/A')

            # Get stream information
            for stream in data.get('streams', []):
                if stream['codec_type'] == 'video':
                    self.video_codec = stream.get('codec_name', 'N/A')
                    self.resolution = f"{stream.get('width', 'N/A')}x{stream.get('height', 'N/A')}"
                elif stream['codec_type'] == 'audio':
                    self.audio_codec = stream.get('codec_name', 'N/A')
        except Exception as e:
            logging.error(f"Error fetching metadata: {str(e)}")

    def format_filesize(self) -> str:
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.filesize < 1024:
                return f"{self.filesize:.2f} {unit}"
            self.filesize /= 1024
        return f"{self.filesize:.2f} TB"

    def format_duration(self) -> str:
        minutes, seconds = divmod(self.duration, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"


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
        self.setWindowTitle("Video Converter with Metadata")
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)
        self.metadata_cache: Dict[str, VideoMetadata] = {}
        self.init_ui()
        self.current_converter = None

    def init_ui(self):
        main_layout = QVBoxLayout()

        # File Selection Area
        file_group = QGroupBox("Files")
        file_layout = QVBoxLayout()

        # File List
        self.file_list = DragDropListWidget()
        file_layout.addWidget(self.file_list)

        # Add/Clear Buttons
        button_layout = QHBoxLayout()
        self.add_file_button = QPushButton("Add Files")
        self.add_file_button.clicked.connect(self.add_files_dialog)
        self.clear_button = QPushButton("Clear List")
        self.clear_button.clicked.connect(self.clear_files)
        button_layout.addWidget(self.add_file_button)
        button_layout.addWidget(self.clear_button)
        file_layout.addLayout(button_layout)

        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)

        # Metadata Table
        metadata_group = QGroupBox("File Information")
        metadata_layout = QVBoxLayout()
        self.metadata_table = QTableWidget()
        self.metadata_table.setColumnCount(7)
        self.metadata_table.setHorizontalHeaderLabels([
            "Filename", "Size", "Duration", "Video Codec",
            "Audio Codec", "Resolution", "Bitrate"
        ])
        self.metadata_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        metadata_layout.addWidget(self.metadata_table)
        metadata_group.setLayout(metadata_layout)
        main_layout.addWidget(metadata_group)

        # Conversion Settings
        settings_group = QGroupBox("Conversion Settings")
        settings_layout = QHBoxLayout()

        # Format Selection
        format_layout = QVBoxLayout()
        format_layout.addWidget(QLabel("Target Format:"))
        self.format_dropdown = QComboBox()
        self.format_dropdown.addItems(['mp4', 'mov', 'mkv', 'avi', 'webm'])
        format_layout.addWidget(self.format_dropdown)
        settings_layout.addLayout(format_layout)

        # Audio Settings
        audio_layout = QVBoxLayout()
        audio_layout.addWidget(QLabel("Audio Settings:"))
        self.audio_setting = QComboBox()
        self.audio_setting.addItems([
            "Copy Audio (Lossless)",
            "Convert to AAC",
            "Convert to MP3",
            "No Audio"
        ])
        audio_layout.addWidget(self.audio_setting)
        settings_layout.addLayout(audio_layout)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # Start Button
        self.start_button = QPushButton("Start Conversion")
        self.start_button.clicked.connect(self.start_conversion)
        main_layout.addWidget(self.start_button)

        # Progress Area
        progress_group = QGroupBox("Conversion Progress")
        self.progress_layout = QVBoxLayout()
        progress_group.setLayout(self.progress_layout)
        main_layout.addWidget(progress_group)

        self.setLayout(main_layout)

    def clear_files(self):
        self.file_list.clear()
        self.metadata_table.setRowCount(0)
        self.metadata_cache.clear()

    def add_files(self, files):
        if not files:
            return

        existing_files = set(self.file_list.item(i).text() for i in range(self.file_list.count()))
        new_files = [f for f in files if f not in existing_files]

        for file in new_files:
            item = QListWidgetItem(file)
            self.file_list.addItem(item)
            self.add_metadata(file)

    def add_metadata(self, filepath: str):
        metadata = VideoMetadata(filepath)
        self.metadata_cache[filepath] = metadata

        row = self.metadata_table.rowCount()
        self.metadata_table.insertRow(row)

        self.metadata_table.setItem(row, 0, QTableWidgetItem(metadata.filename))
        self.metadata_table.setItem(row, 1, QTableWidgetItem(metadata.format_filesize()))
        self.metadata_table.setItem(row, 2, QTableWidgetItem(metadata.format_duration()))
        self.metadata_table.setItem(row, 3, QTableWidgetItem(metadata.video_codec))
        self.metadata_table.setItem(row, 4, QTableWidgetItem(metadata.audio_codec))
        self.metadata_table.setItem(row, 5, QTableWidgetItem(metadata.resolution))
        self.metadata_table.setItem(row, 6, QTableWidgetItem(
            f"{int(float(metadata.bitrate) / 1000) if metadata.bitrate != 'N/A' else 'N/A'} kbps"))

    def add_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Video Files",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*.*)"
        )
        self.add_files(files)

    def get_audio_settings(self):
        audio_option = self.audio_setting.currentText()
        if audio_option == "Copy Audio (Lossless)":
            return ['-c:a', 'copy']
        elif audio_option == "Convert to AAC":
            return ['-c:a', 'aac', '-b:a', '192k']
        elif audio_option == "Convert to MP3":
            return ['-c:a', 'libmp3lame', '-b:a', '192k']
        else:  # No Audio
            return ['-an']

    def start_conversion(self):
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "Warning", "Please add files to convert.")
            return

        target_format = self.format_dropdown.currentText()
        target_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not target_dir:
            return

        # Clear previous progress bars
        for i in reversed(range(self.progress_layout.count())):
            self.progress_layout.itemAt(i).widget().deleteLater()

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

            # Add audio settings to conversion
            audio_settings = self.get_audio_settings()
            self.current_converter.add_file(input_path, output_path, audio_settings)

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
        self.audio_setting.setEnabled(enabled)

    def update_progress(self, file_path, progress):
        progress_bars = [self.progress_layout.itemAt(i).widget() for i in range(self.progress_layout.count())]
        for bar in progress_bars:
            if Path(file_path).name in bar.text():
                bar.setValue(progress)
                break

    def finish_conversion(self, file_path):
        progress_bars = [self.progress_layout.itemAt(i).widget() for i in range(self.progress_layout.count())]
        for bar in progress_bars:
            if Path(file_path).name in bar.text():
                bar.setValue(100)
                break
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

    def add_file(self, input_path, output_path, audio_settings):
        self.conversion_queue.append((input_path, output_path, audio_settings))

    def run(self):
        for input_path, output_path, audio_settings in self.conversion_queue:
            try:
                logging.info(f"Starting conversion: {input_path} -> {output_path}")
                self.convert(input_path, output_path, audio_settings)
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