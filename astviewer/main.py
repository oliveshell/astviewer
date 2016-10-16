"""
   Program that shows the program on the right and its abstract syntax tree (ast) on the left.
"""
from __future__ import print_function
                
import sys, logging, ast, traceback

from astviewer.misc import get_qapplication_instance, class_name, get_qsettings
from astviewer.misc import ABOUT_MESSAGE, PROGRAM_NAME, DEBUGGING
from astviewer.qtpy import QtCore, QtGui, QtWidgets
from astviewer.qtpy.compat import getopenfilename
from astviewer.editor import SourceEditor
from astviewer.tree import SyntaxTreeWidget


logger = logging.getLogger(__name__)


def view(*args, **kwargs):
    """ Opens an AstViewer window
    """
    app = get_qapplication_instance()
    
    window = AstViewer(*args, **kwargs)
    window.show()

    if 'darwin' in sys.platform:
        window.raise_()
        
    logger.info("Starting the AST event loop.")
    exit_code = app.exec_()
    logger.info("AST viewer done...")
    return exit_code



# The main window inherits from a Qt class, therefore it has many
# ancestors public methods and attributes.
# pylint: disable=R0901, R0902, R0904, W0201, R0913


class AstViewer(QtWidgets.QMainWindow):
    """ The main application.
    """

    def __init__(self, file_name = '', source_code = '', mode='exec', reset=False):
        """ Constructor
            
            AST browser windows that displays the Abstract Syntax Tree
            of source code. 
            
            The source can be given as text in the source parameter, or
            can be read from a file. The file_name parameter overrides
            the source parameter.
            
            The mode argument specifies what kind of code must be compiled; 
            it can be 'exec' if source consists of a sequence of statements, 
            'eval' if it consists of a single expression, or 'single' if it 
            consists of a single interactive statement (in the latter case, 
            expression statements that evaluate to something other than None 
            will be printed).
            (see http://docs.python.org/2/library/functions.html#compile)
            
            If reset is True, the persistent settings (e.g. window size) are
            reset to their default values.
        """
        super(AstViewer, self).__init__()
        
        valid_modes = ['exec', 'eval', 'single']
        if mode not in valid_modes:
            raise ValueError("Mode must be one of: {}".format(valid_modes))
        
        # Models
        self._file_name = '<source>'
        self._source_code = source_code
        self._mode = mode
        
        # Views
        self._setup_menu()
        self._setup_views(reset=reset)
        self.setWindowTitle('{}'.format(PROGRAM_NAME))
        
        # Update views
        if file_name and source_code:
            logger.warning("Both the file_name and source_code are defined: source_code ignored.")

        if file_name:
            self._load_file(file_name)

        self._update_widgets()


    def _setup_menu(self):
        """ Sets up the main menu.
        """
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction("&Open File...", self.open_file, "Ctrl+O")
        file_menu.addAction("&Close File", self.close_file)
        file_menu.addAction("E&xit", self.quit_application, "Ctrl+Q")
        
        if DEBUGGING is True:
            file_menu.addSeparator()
            file_menu.addAction("&Test", self.my_test, "Ctrl+T")
        
        self.view_menu = self.menuBar().addMenu("&View")

        self.menuBar().addSeparator()
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction('&About', self.about)


    def _setup_views(self, reset=False):
        """ Creates the UI widgets. 
        """
        self.central_splitter = QtWidgets.QSplitter(self, orientation = QtCore.Qt.Horizontal)
        self.setCentralWidget(self.central_splitter)

        self.ast_tree = SyntaxTreeWidget()
        self.central_splitter.addWidget(self.ast_tree)

        # Add toggling of tree columns to the View menu
        for action in self.ast_tree.get_header_context_menu_actions():
            self.view_menu.addAction(action)

        self.editor = SourceEditor()
        self.central_splitter.addWidget(self.editor)
        
        self.central_splitter.setCollapsible(0, False)
        self.central_splitter.setCollapsible(1, False)
        self.central_splitter.setSizes([600, 500])
        self.central_splitter.setStretchFactor(0, 0.5)
        self.central_splitter.setStretchFactor(1, 0.5)

        # Read persistent settings
        self._readViewSettings(reset = reset)

        # Connect signals
        self.ast_tree.currentItemChanged.connect(self.highlight_node)
        self.editor.sigDoubleClicked.connect(self.ast_tree.select_node)


    def finalize(self):
        """ Cleanup resources.
        """
        logger.debug("Cleaning up resources.")
        self.editor.sigDoubleClicked.disconnect(self.ast_tree.select_node)
        self.ast_tree.currentItemChanged.disconnect(self.highlight_node)


    def close_file(self):
        """ Clears the widgets """
        self._file_name = ""
        self._source_code = ""
        self.editor.clear()
        self.ast_tree.clear()
        self.setWindowTitle('{}'.format(PROGRAM_NAME))

    
    def open_file(self, file_name=None):
        """ Opens a Python file. Show the open file dialog if file_name is None.
        """
        if not file_name:
            file_name = self._get_file_name_from_dialog()

        if file_name:
            self._load_file(file_name)

        self._update_widgets()


    def _get_file_name_from_dialog(self):
        """ Opens a file dialog and returns the file name selected by the user
        """
        file_name, _ = getopenfilename(self, "Open File", '', "Python Files (*.py);;All Files (*)")
        return file_name

    
    def _update_widgets(self):
        """ Updates the tree and editor widgets.
        """            
        self.setWindowTitle('{} - {}'.format(PROGRAM_NAME, self._file_name))
        self.editor.setPlainText(self._source_code)

        if not self._source_code:
            logger.debug("Empty source code, use empty tree.")
            self.ast_tree.clear()
            return

        try:
            syntax_tree = ast.parse(self._source_code, filename=self._file_name, mode=self._mode)
        except Exception as ex:
            if DEBUGGING:
                raise
            else:
                stack_trace = traceback.format_exc()
                msg = "Unable to parse file: {}\n\n{}\n\n{}" \
                    .format(self._file_name, ex, stack_trace)
                logger.exception(ex)
                QtWidgets.QMessageBox.warning(self, 'error', msg)
        else:
            self.ast_tree.populate(syntax_tree, root_label=self._file_name)

        
                
    def _load_file(self, file_name):
        """ Opens a file and sets self._file_name and self._source code if succesful
        """
        logger.debug("Opening {!r}".format(file_name))
        
        in_file = QtCore.QFile(file_name)
        if in_file.open(QtCore.QFile.ReadOnly | QtCore.QFile.Text):
            text = in_file.readAll()
            try:
                source_code = str(text, encoding='utf-8')  # Python 3
            except TypeError:
                source_code = str(text)                    # Python 2
                
            self._file_name = file_name
            self._source_code = source_code
            
        else:
            msg = "Unable to open file: {}".format(file_name)
            logger.warning(msg)
            QtWidgets.QMessageBox.warning(self, 'error', msg)
            


    @QtCore.Slot(QtWidgets.QTreeWidgetItem, QtWidgets.QTreeWidgetItem)
    def highlight_node(self, current_item, _previous_item):
        """ Highlights the node if it has line:col information.
        """
        if current_item:
            highlight_str = current_item.text(SyntaxTreeWidget.COL_HIGHLIGHT)
            from_line_str, from_col_str, to_line_str, to_col_str = highlight_str.split(":")

            try:
                from_line_col = (int(from_line_str), int(from_col_str))
            except ValueError:
                from_line_col = None

            try:
                to_line_col = (int(to_line_str), int(to_col_str))
            except ValueError:
                to_line_col = None
        else:
            from_line_col = to_line_col =(0, 0)

        logger.debug("Highlighting ({!r}) : ({!r})".format(from_line_col, to_line_col))
        self.editor.select_text(from_line_col, to_line_col)


    def _readViewSettings(self, reset=False):
        """ Reads the persistent program settings

            :param reset: If True, the program resets to its default settings
        """
        pos = QtCore.QPoint(30, 30)
        window_size = QtCore.QSize(1300, 700)  # Assumes minimal resolution of 1366 x 768

        header = self.ast_tree.header()
        header_restored = False

        if reset:
            logger.debug("Resetting persistent view settings")
        else:
            logger.debug("Reading view settings")
            settings = get_qsettings()
            settings.beginGroup('view')
            pos = settings.value("main_window/pos", pos)
            window_size = settings.value("main_window/size", window_size)
            splitter_state = settings.value("central_splitter/state")
            if splitter_state:
                self.central_splitter.restoreState(splitter_state)
            header_restored = self.ast_tree.read_view_settings('tree/header_state', settings, reset)
            settings.endGroup()

        if not header_restored:

            header.resizeSection(SyntaxTreeWidget.COL_NODE, 250)
            header.resizeSection(SyntaxTreeWidget.COL_FIELD, 80)
            header.resizeSection(SyntaxTreeWidget.COL_CLASS, 80)
            header.resizeSection(SyntaxTreeWidget.COL_VALUE, 80)
            header.resizeSection(SyntaxTreeWidget.COL_POS, 80)
            header.resizeSection(SyntaxTreeWidget.COL_HIGHLIGHT, 100)

            for idx in range(len(AstViewer.HEADER_LABELS)):
                visible = False if idx == SyntaxTreeWidget.COL_HIGHLIGHT else True
                self.ast_tree.toggle_column_actions_group.actions()[idx].setChecked(visible)

        self.resize(window_size)
        self.move(pos)


    def _writeViewSettings(self):
        """ Writes the view settings to the persistent store
        """
        logger.debug("Writing view settings for window")

        settings = get_qsettings()
        settings.beginGroup('view')
        self.ast_tree.write_view_settings("tree/header_state", settings)
        settings.setValue("central_splitter/state", self.central_splitter.saveState())
        settings.setValue("main_window/pos", self.pos())
        settings.setValue("main_window/size", self.size())
        settings.endGroup()


    def my_test(self):
        """ Function for testing """
        logger.debug("Test function called.")


    def about(self):
        """ Shows the about message window. """
        QtWidgets.QMessageBox.about(self, "About %s" % PROGRAM_NAME, ABOUT_MESSAGE)


    def closeEvent(self, event):
        """ Called when the window is closed
        """
        logger.debug("closeEvent")
        self._writeViewSettings()
        self.finalize()
        self.close()
        event.accept()
        logger.debug("Closed {}".format(PROGRAM_NAME))


    def quit_application(self):
        """ Closes all windows """
        app = QtWidgets.QApplication.instance()
        app.closeAllWindows()
