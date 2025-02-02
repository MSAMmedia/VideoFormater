import sys
import os
import subprocess
import logging
import json
from pathlib import Path
from typing import Dict, Optional
from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QMimeDatabase, QUrl,
    QParallelAnimationGroup, QPropertyAnimation,
    QEasingCurve
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QListWidget, QComboBox, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QMessageBox, QProgressBar, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QCheckBox, QGroupBox, QHeaderView, QSizePolicy, QMainWindow, QMenuBar, QMenu,
    QDialog, QVBoxLayout, QTextBrowser, QSlider
)
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap


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
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
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
            self.main_window.add_files(files)  # Use the stored reference
            event.acceptProposedAction()
        else:
            event.ignore()


class VideoConverter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Converter with Metadata")
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)

        # Initialize variables
        self.metadata_cache: Dict[str, VideoMetadata] = {}
        self.current_converter = None
        self.version = "1.0.0"

        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Create layout for central widget
        self.main_layout = QVBoxLayout()

        # Create menus and UI
        self.create_menu_bar()
        self.init_ui()

        # Set the layout to the central widget
        self.central_widget.setLayout(self.main_layout)

    def create_menu_bar(self):
        menubar = self.menuBar()

        # Help Menu
        help_menu = menubar.addMenu("Help")

        # Add Help action
        help_action = help_menu.addAction("Help")
        help_action.triggered.connect(self.show_help)

        # About Menu
        about_menu = menubar.addMenu("About")

        # Add About action
        about_action = about_menu.addAction("About")
        about_action.triggered.connect(self.show_about)

    def show_help(self):
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("Help")
        help_dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout()
        text_browser = QTextBrowser()

        help_text = """
        <h2>LosslessTranscoder Help</h2>

        <h3>Features:</h3>
        <ul>
            <li>Lossless video conversion between different container formats</li>
            <li>Support for multiple video formats (MP4, MOV, MKV, AVI, WEBM)</li>
            <li>Drag and drop file support</li>
            <li>Detailed file information and metadata display</li>
            <li>Multiple audio handling options:
                <ul>
                    <li>Copy Audio (Lossless)</li>
                    <li>Convert to AAC</li>
                    <li>Convert to MP3</li>
                    <li>No Audio</li>
                </ul>
            </li>
            <li>Batch processing support</li>
            <li>Progress tracking for each conversion</li>
        </ul>

        <h3>How to Use:</h3>
        <ol>
            <li>Add video files using the "Add Files" button or drag and drop</li>
            <li>View file information in the collapsible metadata panel</li>
            <li>Select your desired output format</li>
            <li>Choose audio handling method</li>
            <li>Click "Start Conversion" and select output directory</li>
            <li>Monitor progress in the conversion progress area</li>
        </ol>
        """

        text_browser.setHtml(help_text)
        layout.addWidget(text_browser)
        help_dialog.setLayout(layout)
        help_dialog.exec()

    def show_about(self):
        about_dialog = QDialog(self)
        about_dialog.setWindowTitle("About")
        about_dialog.setFixedSize(400, 300)

        layout = QVBoxLayout()

        # App Icon
        icon_label = QLabel()
        # Placeholder for app icon. Either provide a real one or remove it.
        icon_pixmap = QPixmap()  # This will be a blank icon.
        icon_label.setPixmap(icon_pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # App Information
        info_text = QTextBrowser()
        info_text.setOpenExternalLinks(True)
        info_text.setHtml(f"""
        <div style='text-align: center;'>
            <h2>LosslessTranscoder</h2>
            <p>Version {self.version}</p>
            <p>A lossless video converter with advanced metadata support.</p>
            <p>© 2015 by MSAM.media - Thomas Liebl</p>
        </div>
        """)

        layout.addWidget(icon_label)
        layout.addWidget(info_text)
        about_dialog.setLayout(layout)
        about_dialog.exec()

    def init_ui(self):
        # File Selection Area
        file_group = QGroupBox("Files")
        file_layout = QVBoxLayout()

        # File List
        self.file_list = DragDropListWidget(self)
        file_layout.addWidget(self.file_list)

        # Add/Clear Buttons
        button_layout = QHBoxLayout()
        self.add_file_button = QPushButton("Add Files")
        self.add_file_button.clicked.connect(self.add_files_dialog)
        self.clear_button = QPushButton("Clear List")
        self.clear_button.clicked.connect(self.clear_files)

        # Apply button style
        self.apply_macos_button_style(self.add_file_button)
        self.apply_macos_button_style(self.clear_button)

        button_layout.addWidget(self.add_file_button)
        button_layout.addWidget(self.clear_button)
        file_layout.addLayout(button_layout)

        file_group.setLayout(file_layout)
        self.main_layout.addWidget(file_group)

        # Metadata Table in Collapsible Box
        self.metadata_box = CollapsibleBox("File Information")
        metadata_layout = QVBoxLayout()
        self.metadata_table = QTableWidget()
        self.metadata_table.setColumnCount(7)
        self.metadata_table.setHorizontalHeaderLabels([
            "Filename", "Size", "Duration", "Video Codec",
            "Audio Codec", "Resolution", "Bitrate"
        ])
        self.metadata_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        metadata_layout.addWidget(self.metadata_table)
        self.metadata_box.set_content_layout(metadata_layout)
        self.main_layout.addWidget(self.metadata_box)

        # Rest of the UI code remains the same...

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

        # Target Size Slider
        size_layout = QVBoxLayout()
        size_layout.addWidget(QLabel("Target Size (MB):"))
        self.target_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_size_slider.setMinimum(10)  # Minimum size 10MB
        self.target_size_slider.setMaximum(5000)  # Maximum size 5000MB
        self.target_size_slider.setValue(100)  # Default value 100MB
        self.target_size_slider.valueChanged.connect(self.update_target_size_label)
        size_layout.addWidget(self.target_size_slider)

        self.target_size_label = QLabel("100 MB")
        size_layout.addWidget(self.target_size_label)

        settings_layout.addLayout(size_layout)

        settings_group.setLayout(settings_layout)
        self.main_layout.addWidget(settings_group)

        # Start/Cancel Buttons
        button_layout_start_cancel = QHBoxLayout()
        self.start_button = QPushButton("Start Conversion")
        self.start_button.clicked.connect(self.start_conversion)
        self.apply_macos_button_style(self.start_button)

        self.cancel_button = QPushButton("Cancel Conversion")
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.cancel_button.setEnabled(False)
        self.apply_macos_button_style(self.cancel_button)

        button_layout_start_cancel.addWidget(self.start_button)
        button_layout_start_cancel.addWidget(self.cancel_button)

        self.main_layout.addLayout(button_layout_start_cancel)

        # Progress Area
        progress_group = QGroupBox("Conversion Progress")
        self.progress_layout = QVBoxLayout()
        progress_group.setLayout(self.progress_layout)
        self.main_layout.addWidget(progress_group)

    def update_target_size_label(self, value):
        self.target_size_label.setText(f"{value} MB")

    def apply_macos_button_style(self, button: QPushButton):
        button.setStyleSheet("""
          QPushButton {
              background-color: #1665DC; /* Blue background */
              border: 1px solid #174F9B; /* Darker blue border */
              border-radius: 4px;
              padding: 6px 12px;
              font-size: 14px;
              color: white; /* White text color */
          }
          QPushButton:hover {
              background-color: #174F9B; /* Slightly darker blue on hover */
          }
          QPushButton:pressed {
              background-color: #1f618d; /* Even darker blue when pressed */
          }
          QPushButton:focus {
              outline: none;
          }
      """)

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

        # Enable cancel button
        self.cancel_button.setEnabled(True)

        # Get target size in MB
        target_size_mb = self.target_size_slider.value()

        # Create new converter instance
        self.current_converter = Converter(target_size_mb)

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

    def cancel_conversion(self):
        if self.current_converter:
            self.current_converter.stop()
            self.current_converter = None  # Clear the reference
            self.toggle_ui(True)
            self.cancel_button.setEnabled(False)  # Disable cancel button
            QMessageBox.information(self, "Cancelled", "Conversion has been canceled.")
        else:
            QMessageBox.warning(self, "Warning", "No active conversion to cancel.")

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
        self.cancel_button.setEnabled(False)  # Disable cancel button
        QMessageBox.information(self, "Complete", "All conversions finished!")
        logging.info("All conversions completed")


class Converter(QThread):
    progress_signal = pyqtSignal(str, int)
    finished_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str, str)
    all_finished_signal = pyqtSignal()

    def __init__(self, target_size_mb):
        super().__init__()
        self.conversion_queue = []
        self.is_stopped = False
        self.target_size_mb = target_size_mb

    def add_file(self, input_path, output_path, audio_settings):
        self.conversion_queue.append((input_path, output_path, audio_settings))

    def run(self):
        for input_path, output_path, audio_settings in self.conversion_queue:
            if self.is_stopped:
                break
            try:
                logging.info(f"Starting conversion: {input_path} -> {output_path}")
                self.convert(input_path, output_path, audio_settings, self.target_size_mb)
                self.finished_signal.emit(input_path)
            except Exception as e:
                logging.error(f"Conversion error for {input_path}: {str(e)}")
                self.error_signal.emit(input_path, str(e))

        if not self.is_stopped:
            self.all_finished_signal.emit()
        self.is_stopped = False  # reset

    def convert(self, input_path, output_path, audio_settings, target_size_mb):
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

            # Calculate target size in bytes
            target_size_bytes = target_size_mb * 1024 * 1024

            # First pass
            cmd_pass1 = [
                'ffmpeg',
                '-y',
                '-i', input_path,
                '-c:v', 'libvpx-vp9' if output_path.lower().endswith('.webm') else 'libx264',
                '-pass', '1',
                '-an',  # No audio in first pass
                '-f', 'null',  # no output file in first pass
                os.devnull,
            ]

            # Check if output format is webm
            if output_path.lower().endswith('.webm'):
                cmd_pass1.extend([
                    '-c:v', 'libvpx-vp9',
                    '-b:v', '20M',
                ])
            else:
                cmd_pass1.extend([
                    '-c:v', 'libx264',  # for mp4 ect.
                    '-b:v', '20M',
                ])

            subprocess.run(cmd_pass1, check=True, capture_output=True)

            # Calculate bitrate for second pass (using maxrate to limit bitrate)
            total_bitrate_bps = int((target_size_bytes * 8) / duration)
            video_bitrate_bps = int(total_bitrate_bps)

            cmd_pass2 = [
                'ffmpeg',
                '-y',
                '-i', input_path,
                '-c:v', 'libvpx-vp9' if output_path.lower().endswith('.webm') else 'libx264',
                '-pass', '2',
                '-b:v', f'{video_bitrate_bps}k',
                '-maxrate', f'{video_bitrate_bps}k',
                '-c:a', 'libvorbis' if output_path.lower().endswith('.webm') else 'aac',
                '-b:a', '128k'

            ]

            # Check if output format is webm
            if not output_path.lower().endswith('.webm'):
                cmd_pass2.extend(audio_settings)  # use audio_settings for non-webm formats

            cmd_pass2.append(output_path)

            # Start conversion process
            process = subprocess.Popen(
                cmd_pass2,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # Monitor conversion progress
            while True:
                if self.is_stopped:
                    process.terminate()
                    break
                line = process.stderr.readline()
                if not line and process.poll() is not None:
                    break

                if 'time=' in line:
                    current_time = self.parse_time(line)
                    if current_time > 0:
                        progress = min(int((current_time / duration) * 100), 100)
                        self.progress_signal.emit(input_path, progress)
            # Check if conversion was successful
            if process.returncode != 0 and not self.is_stopped:
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

    def stop(self):
        self.is_stopped = True


class CollapsibleBox(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)

        # Create horizontal layout for button content
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)

        # Create arrow label
        self.arrow = QLabel("▶")  # Right-pointing triangle
        self.arrow.setStyleSheet("""
            QLabel {
                padding: 5px;
                font-size: 12px;
            }
        """)

        # Create title label
        title_label = QLabel(title)
        title_label.setStyleSheet("padding: 5px;")

        # Add arrow and title to button layout
        button_layout.addWidget(self.arrow)
        button_layout.addWidget(title_label)
        button_layout.addStretch()

        # Create button and set its layout
        self.toggle_button = QPushButton()
        self.toggle_button.setLayout(button_layout)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 5px;
                border: none;
                 background-color: #1665DC; /* Blue background */
                 color: white;
            }
            QPushButton:hover {
                 background-color: #174F9B; /* Slightly darker blue on hover */
            }
        """)
        self.toggle_button.clicked.connect(self.on_clicked)

        self.toggle_animation = QParallelAnimationGroup(self)

        self.content_area = QWidget()
        self.content_area.setMaximumHeight(0)
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        lay = QVBoxLayout(self)
        lay.setSpacing(0)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.toggle_button)
        lay.addWidget(self.content_area)

        self.content_layout = QVBoxLayout()
        self.content_area.setLayout(self.content_layout)

        self.is_collapsed = True

    def on_clicked(self):
        self.toggle_collapse()
        # Update arrow when clicked
        if self.is_collapsed:
            self.arrow.setText("▶")  # Right-pointing triangle
        else:
            self.arrow.setText("▼")  # Down-pointing triangle

    def toggle_collapse(self):
        content_height = self.content_layout.sizeHint().height()
        self.is_collapsed = not self.is_collapsed

        if not self.is_collapsed:
            maximum_height = content_height
        else:
            maximum_height = 0

        animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        animation.setDuration(300)
        animation.setStartValue(self.content_area.maximumHeight())
        animation.setEndValue(maximum_height)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuart)

        self.toggle_animation.clear()
        self.toggle_animation.addAnimation(animation)
        self.toggle_animation.start()

    def set_content_layout(self, layout):
        QWidget().setLayout(self.content_layout)
        self.content_layout = layout
        self.content_area.setLayout(self.content_layout)


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