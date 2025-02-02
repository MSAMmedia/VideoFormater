import sys
import os
import subprocess
import logging
import json
from pathlib import Path
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QMimeDatabase, QUrl
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QListWidget, QComboBox, QPushButton,
    QFileDialog, QVBoxLayout, QHBoxLayout, QMessageBox, QProgressBar, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QCheckBox, QGroupBox, QHeaderView, QSizePolicy, QMainWindow, QMenuBar, QMenu,
    QDialog, QTextBrowser, QSlider, QLineEdit, QRadioButton, QButtonGroup, QAbstractItemView
)
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPixmap, QAction

from PyQt6.QtCore import QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup

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
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
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
        except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logging.error(f"Error fetching metadata for {self.filepath}: {str(e)}")

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
            self.main_window.add_files(files)
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
        self.size_reduction_method_selected = "Single-Pass Encoding"  # default

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
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.add_files_dialog)
        file_menu.addAction(open_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def add_files_dialog(self):
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        file_dialog.setNameFilter("Video Files (*.mp4 *.mov *.mkv *.avi *.webm)")
        if file_dialog.exec():
            files = file_dialog.selectedFiles()
            self.add_files(files)

    def show_about_dialog(self):
        QMessageBox.about(self, "About Video Converter", "Video Converter with Metadata\nVersion 1.0.0")

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

        # Target Size Controls
        size_layout = QVBoxLayout()
        self.enable_size_control = QCheckBox("Enable Target Size")
        self.enable_size_control.setChecked(False)  # Ensure it starts unchecked
        size_layout.addWidget(self.enable_size_control)

        # Create radio buttons
        size_radio_layout = QVBoxLayout()
        self.size_reduction_method = QButtonGroup(self)  # Add self as parent

        self.single_pass_radio = QRadioButton("Single-Pass Encoding")
        self.single_pass_radio.setChecked(True)
        self.single_pass_radio.setEnabled(False)  # Start disabled
        size_radio_layout.addWidget(self.single_pass_radio)
        self.size_reduction_method.addButton(self.single_pass_radio)

        self.two_pass_radio = QRadioButton("Two-Pass Encoding")
        self.two_pass_radio.setEnabled(False)  # Start disabled
        size_radio_layout.addWidget(self.two_pass_radio)
        self.size_reduction_method.addButton(self.two_pass_radio)

        size_layout.addLayout(size_radio_layout)

        # Create slider controls
        size_slider_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Target Size (MB):"))
        self.target_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.target_size_slider.setMinimum(10)
        self.target_size_slider.setMaximum(5000)
        self.target_size_slider.setValue(100)
        self.target_size_slider.setEnabled(False)  # Start disabled
        self.target_size_slider.valueChanged.connect(self.update_target_size_value)
        size_slider_layout.addWidget(self.target_size_slider)

        self.target_size_input = QLineEdit()
        self.target_size_input.setText("100")
        self.target_size_input.setEnabled(False)  # Start disabled
        self.target_size_input.textChanged.connect(self.update_target_size_slider)
        size_slider_layout.addWidget(self.target_size_input)

        size_layout.addLayout(size_slider_layout)

        self.target_size_label = QLabel("N/A")  # Start with N/A since it's disabled
        size_layout.addWidget(self.target_size_label)

        # Connect the checkbox after all controls are set up
        self.enable_size_control.stateChanged.connect(self.toggle_size_controls)
        self.size_reduction_method.buttonClicked.connect(self.update_size_reduction_method)  # connect

        settings_layout.addLayout(size_layout)
        settings_group.setLayout(settings_layout)
        self.main_layout.addWidget(settings_group)

        # Create Dimension Resize collapsible box
        self.resize_box = CollapsibleBox("Dimension Resize")
        resize_layout = QVBoxLayout()

        # Preset Resolutions
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("Preset Resolutions:"))
        self.resolution_dropdown = QComboBox()
        self.resolution_dropdown.addItem("Select Preset")
        self.resolution_dropdown.addItems(["1080p (1920x1080)", "720p (1280x720)", "480p (854x480)", "360p (640x360)"])
        self.resolution_dropdown.currentIndexChanged.connect(self.set_preset_resolution)
        resolution_layout.addWidget(self.resolution_dropdown)
        resize_layout.addLayout(resolution_layout)

        # Width and Height input
        dimension_layout = QHBoxLayout()
        dimension_layout.addWidget(QLabel("Width (px):"))
        self.width_input = QLineEdit()
        self.width_input.setPlaceholderText("Width")
        dimension_layout.addWidget(self.width_input)

        dimension_layout.addWidget(QLabel("Height (px):"))
        self.height_input = QLineEdit()
        self.height_input.setPlaceholderText("Height")
        dimension_layout.addWidget(self.height_input)

        resize_layout.addLayout(dimension_layout)

        # Aspect Ratio Handling
        aspect_ratio_layout = QHBoxLayout()
        aspect_ratio_layout.addWidget(QLabel("Aspect Ratio:"))
        self.aspect_ratio_dropdown = QComboBox()
        self.aspect_ratio_dropdown.addItems(["Maintain Aspect Ratio (Black Bars)", "Crop to Fit"])
        aspect_ratio_layout.addWidget(self.aspect_ratio_dropdown)
        resize_layout.addLayout(aspect_ratio_layout)

        # Allow Upscaling
        self.allow_upscaling_checkbox = QCheckBox("Allow Upscaling (May Reduce Quality)")
        resize_layout.addWidget(self.allow_upscaling_checkbox)

        self.resize_box.set_content_layout(resize_layout)
        self.main_layout.addWidget(self.resize_box)

        # Connect signals for manual width/height input
        self.width_input.textChanged.connect(self.reset_preset_dropdown)
        self.height_input.textChanged.connect(self.reset_preset_dropdown)
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

    def apply_macos_button_style(self, button):
        button.setStyleSheet("""
                QPushButton {
                    background-color: #007AFF;
                    color: white;
                    border-radius: 5px;
                    padding: 5px 10px;
                }
                QPushButton:pressed {
                    background-color: #005BB5;
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
        if filepath in self.metadata_cache:
            return  # Already added

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

    def update_target_size_value(self, value):
        self.target_size_input.setText(str(value))
        self.target_size_label.setText(f"{value} MB")

    def update_target_size_slider(self, text):
        try:
            value = int(text)
            if 10 <= value <= 5000:
                self.target_size_slider.setValue(value)
                self.target_size_label.setText(f"{value} MB")
            else:
                self.target_size_input.setText(str(self.target_size_slider.value()))
        except ValueError:
            self.target_size_input.setText(str(self.target_size_slider.value()))

    def toggle_size_controls(self, state):
        is_checked = state == Qt.CheckState.Checked.value

        self.target_size_slider.setEnabled(is_checked)
        self.target_size_input.setEnabled(is_checked)
        self.single_pass_radio.setEnabled(is_checked)
        self.two_pass_radio.setEnabled(is_checked)

        if is_checked:
            self.target_size_label.setText(f"{self.target_size_slider.value()} MB")
        else:
            self.target_size_label.setText("N/A")

    def update_size_reduction_method(self, button):
        self.size_reduction_method_selected = button.text()

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

    def reset_preset_dropdown(self):
        """Resets the preset dropdown to "Select Preset" if manual input is detected."""
        if self.resolution_dropdown.currentIndex() != 0:
            self.resolution_dropdown.setCurrentIndex(0)

    def set_preset_resolution(self):
        preset_text = self.resolution_dropdown.currentText()
        if preset_text == "Select Preset":
            self.width_input.clear()
            self.height_input.clear()
        else:
            width, height = map(int, preset_text.split(' ')[1].replace('(', '').replace(')', '').split('x'))
            self.width_input.setText(str(width))
            self.height_input.setText(str(height))

    def get_resize_settings(self, input_path):
        width_str = self.width_input.text()
        height_str = self.height_input.text()

        # Check if both width and height are provided
        if not width_str or not height_str:
            return []  # Return empty list if no resize is specified

        try:
            target_width = int(width_str)
            target_height = int(height_str)
        except ValueError:
            QMessageBox.warning(self, "Warning", "Invalid width or height value. Please enter integers.")
            return []

        # Get original dimensions using ffprobe
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=s=x:p=0',
                input_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            original_width, original_height = map(int, result.stdout.strip().split('x'))
        except (FileNotFoundError, subprocess.CalledProcessError, ValueError):
            QMessageBox.warning(self, "Warning", "Could not determine original video dimensions.")
            return []

        # Determine scaling behavior
        allow_upscaling = self.allow_upscaling_checkbox.isChecked()
        if allow_upscaling:
            force_original_aspect_ratio = "increase"
        else:
            force_original_aspect_ratio = "decrease"

        # Determine aspect ratio handling
        aspect_ratio_handling = self.aspect_ratio_dropdown.currentText()
        if aspect_ratio_handling == "Maintain Aspect Ratio (Black Bars)":
            scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio={force_original_aspect_ratio}"
            padding_filter = f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black"
            resize_filter = f"{scale_filter},{padding_filter}"
        elif aspect_ratio_handling == "Crop to Fit":
            scale_filter = f"scale={target_width}:{target_height}:force_original_aspect_ratio=increase"
            crop_filter = f"crop={target_width}:{target_height}"
            resize_filter = f"{scale_filter},{crop_filter}"
        else:  # Should not happen, but handle it just in case
            resize_filter = ""

        if resize_filter:
            return ['-vf', resize_filter]
        else:
            return []

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

        # Determine if size control is active
        if self.enable_size_control.isChecked():
            target_size_mb = self.target_size_slider.value()
            self.current_converter = Converter(target_size_mb)
            self.current_converter.size_reduction_method_selected = self.size_reduction_method_selected
        else:
            self.current_converter = Converter()

        # Set up files for conversion
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            input_path = item.text()
            metadata = self.metadata_cache.get(input_path)

            file_name = Path(input_path).stem

            # Construct new filename with metadata
            if metadata:
                video_codec = metadata.video_codec.upper() if metadata.video_codec != 'N/A' else 'unknown'
                audio_codec = metadata.audio_codec.upper() if metadata.audio_codec != 'N/A' else 'unknown'
                resolution = metadata.resolution if metadata.resolution != 'N/A' else 'unknown'
                bitrate = f"{int(float(metadata.bitrate) / 1000)}kbps" if metadata.bitrate != 'N/A' else 'unknown'
                duration = metadata.format_duration()

                new_filename_parts = [
                    file_name,
                    f"[{video_codec}]",
                    f"[{audio_codec}]",
                    f"[{resolution}]",
                    f"[{bitrate}]",
                    f"[{duration}]"
                ]

                max_part_length = 50  # Maximum length for each part of the filename
                new_filename = ""
                current_part = ""

                for part in new_filename_parts:
                    if len(current_part) + len(part) + 1 <= max_part_length:
                        # Add part to current_part if it doesn't exceed the max length
                        current_part += part
                    else:
                        # If current_part is not empty, add it to new_filename
                        if current_part:
                            new_filename += current_part + "_"
                        # Start a new part
                        current_part = part

                # Add the last part to new_filename
                new_filename += current_part

                # Remove trailing underscore if present
                if new_filename.endswith("_"):
                    new_filename = new_filename[:-1]
            else:
                new_filename = file_name

            output_path = str(Path(target_dir) / f"{new_filename}.{target_format}")

            progress_bar = QProgressBar()
            progress_bar.setValue(0)
            progress_bar.setTextVisible(True)
            progress_bar.setFormat(f"%p% - {Path(input_path).name}")
            self.progress_layout.addWidget(progress_bar)

            # Add audio settings to conversion
            audio_settings = self.get_audio_settings()
            resize_settings = self.get_resize_settings(input_path)
            self.current_converter.add_file(input_path, output_path, audio_settings, resize_settings)

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
        self.enable_size_control.setEnabled(enabled)
        self.target_size_slider.setEnabled(enabled and self.enable_size_control.isChecked())
        self.target_size_input.setEnabled(enabled and self.enable_size_control.isChecked())
        self.single_pass_radio.setEnabled(enabled and self.enable_size_control.isChecked())
        self.two_pass_radio.setEnabled(enabled and self.enable_size_control.isChecked())
        self.width_input.setEnabled(enabled)
        self.height_input.setEnabled(enabled)
        self.resolution_dropdown.setEnabled(enabled)
        self.aspect_ratio_dropdown.setEnabled(enabled)
        self.allow_upscaling_checkbox.setEnabled(enabled)

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

            def __init__(self, target_size_mb=None):
                super().__init__()
                self.conversion_queue = []
                self.is_stopped = False
                self.target_size_mb = target_size_mb
                self.size_reduction_method_selected = "Single-Pass Encoding"  # Default

            def add_file(self, input_path, output_path, audio_settings, resize_settings=None):
                self.conversion_queue.append((input_path, output_path, audio_settings, resize_settings))

            def run(self):
                for input_path, output_path, audio_settings, resize_settings in self.conversion_queue:
                    if self.is_stopped:
                        break
                    try:
                        logging.info(f"Starting conversion: {input_path} -> {output_path}")
                        if self.target_size_mb is not None:
                            self.convert(input_path, output_path, audio_settings, self.target_size_mb, resize_settings)
                        else:
                            self.convert(input_path, output_path, audio_settings, resize_settings=resize_settings)
                        self.finished_signal.emit(input_path)
                    except Exception as e:
                        logging.error(f"Conversion error for {input_path}: {str(e)}")
                        self.error_signal.emit(input_path, str(e))

                if not self.is_stopped:
                    self.all_finished_signal.emit()
                self.is_stopped = False  # reset

            def convert(self, input_path, output_path, audio_settings, target_size_mb=None, resize_settings=None):
                try:
                    # Check if ffmpeg is available
                    try:
                        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                    except FileNotFoundError:
                        raise Exception("ffmpeg is not installed or not found in system PATH")
                    except subprocess.CalledProcessError:
                        raise Exception("Error checking ffmpeg version")

                    # Get video duration for progress calculation
                    duration = self.get_video_duration(input_path)
                    if duration == 0:
                        raise Exception("Could not determine video duration")

                    # Prepare ffmpeg command
                    cmd = ['ffmpeg', '-y', '-i', input_path]

                    # Add resize settings if available
                    if resize_settings:
                        cmd.extend(resize_settings)

                    if target_size_mb is not None:
                        target_size_bytes = target_size_mb * 1024 * 1024
                        bitrate_kbps = int((target_size_bytes * 8) / (duration * 1000))
                        bitrate_kbps = max(100, min(bitrate_kbps, 8000))

                        if self.size_reduction_method_selected == "Single-Pass Encoding":
                            cmd.extend([
                                '-c:v', 'libx264',
                                '-b:v', f'{bitrate_kbps}k',
                                '-crf', '23',
                            ])
                        elif self.size_reduction_method_selected == "Two-Pass Encoding":
                            # Two-pass encoding (more complex, needs more parameters)
                            cmd_pass1 = [
                                'ffmpeg', '-y', '-i', input_path,
                                '-c:v', 'libx264', '-pass', '1', '-an', '-f', 'null', '/dev/null'
                            ]
                            subprocess.run(cmd_pass1, check=True, stderr=subprocess.PIPE)

                            cmd.extend([
                                '-c:v', 'libx264', '-pass', '2',
                                '-b:v', f'{bitrate_kbps}k',
                                '-maxrate', f'{bitrate_kbps}k',
                            ])

                        cmd.extend(audio_settings)
                    else:
                        cmd.extend(['-c:v', 'copy'])
                        cmd.extend(audio_settings)

                    cmd.append(output_path)

                    # Start conversion process
                    process = subprocess.Popen(
                        cmd,
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
                    raise Exception(f"Conversion failed for {input_path}: {str(e)}")

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
                    except (FileNotFoundError, subprocess.CalledProcessError) as e:
                        logging.error(f"Error getting video duration for {input_path}: {str(e)}")
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