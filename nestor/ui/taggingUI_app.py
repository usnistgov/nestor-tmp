import importlib

import pandas as pd
import numpy as np
import fuzzywuzzy.process as zz
import shutil


import chardet
import webbrowser

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import seaborn as sns


import nestor.keyword as kex
from nestor.ui.meta_windows import *


neo4j_spec = importlib.util.find_spec("neo4j")
simplecrypt_spec = importlib.util.find_spec("simplecrypt")

dbModule_exists = neo4j_spec is not None and simplecrypt_spec is not None
#dbModule_exists = False

if dbModule_exists:
    from nestor.store_data.database import DatabaseNeo4J
    import neo4j

    #from nestor.ui.menu_app import DialogDatabaseRunQuery
    from nestor.store_data.helper import resultToObservationDataframe


fname = 'taggingUI.ui'
script_dir = Path(__file__).parent
Ui_MainWindow_taggingTool, QtBaseClass_taggingTool = uic.loadUiType(script_dir/fname)
class MyTaggingToolWindow(Qw.QMainWindow, Ui_MainWindow_taggingTool):

    def __init__(self, projectsPath, databaseToCsv_mapping=None, iconPath=None):

        Qw.QMainWindow.__init__(self)
        Ui_MainWindow_taggingTool.__init__(self)

        """
        Instantiate  values
        """
        self.projectsPath = projectsPath

        self.iconPath = iconPath
        if self.iconPath:
            self.setWindowIcon(QtGui.QIcon(self.iconPath))

        self.existingProject =set([folder.name for folder in projectsPath.iterdir() if folder.is_dir()])

        self.config_default = {
            'settings': {
                'numberTokens': 1000,
                'alreadyChecked_threshold': 99,
                'showCkeckBox_threshold': 50
            },
            'csvinfo': {},
            'database': {
                'schema' : str(script_dir.parent / 'store_data' / 'DatabaseSchema.yaml')
            },
            'classification':{
                'mapping':{
                    'I I': 'I',
                    'I P': 'P I',
                    'I S': 'S I',
                    'P I': 'P I',
                    'P P': 'X',
                    'P S': 'X',
                    'S I': 'S I',
                    'S P': 'X',
                    'S S': 'X'
                },
                'type': 'IPSUX'
            }

        }
        self.config = self.config_default.copy()

        self.databaseToCsv_mapping = databaseToCsv_mapping


        """
        Default values
         """
        self.dataframe_Original = None
        self.dataframe_vocab1Gram = None
        self.dataframe_vocabNGram = None

        self.dataframe_completeness = None

        self.database = None

        self.tokenExtractor_1Gram = kex.TokenExtractor()  # sklearn-style TF-IDF calc
        self.tokenExtractor_nGram = kex.TokenExtractor(ngram_range=(2, 2))

        self.clean_rawText_1Gram = None
        self.clean_rawText = None

        self.tag_df = None
        self.relation_df = None
        self.tag_readable = None

        self.dataframe_completeness = None



        """
        UI objects
        """
        self.setupUi(self)
        self.setGeometry(20, 20, 648, 705)

        self.enableFeature(existDatabase=False, existProject=False, existTagExtracted=False)

        self.changeColor = {
            'default': 'background-color: None;',
            'wrongInput' : 'background-color: rgb(255, 51, 0);',
            'updateToken' : 'background-color: rgb(0, 179, 89);'
        }

        self.completenessPlot = MyMplCanvas(self.gridLayout_report_progressPlot, self.tabWidget, self.dataframe_completeness)
        self.horizontalSlider_1gram_FindingThreshold.setValue(self.config['settings'].get('showCkeckBox_threshold',50))

        """"""


        self.classificationDictionary_1Gram = {
            'S': self.radioButton_1gram_SolutionEditor,
            'P': self.radioButton_1gram_ProblemEditor,
            'I': self.radioButton_1gram_ItemEditor,
            'X': self.radioButton_1gram_StopWordEditor,
            'U': self.radioButton_1gram_UnknownEditor,
            '' : self.radioButton_1gram_NotClassifiedEditor
        }
        self.buttonDictionary_1Gram = {
            'Item': 'I',
            'Problem': 'P',
            'Solution': 'S',
            'Ambiguous (Unknown)': 'U',
            'Stop-word': 'X',
            'not yet classified': ''
        }

        self.classificationDictionary_NGram = {
            'S I': self.radioButton_Ngram_SolutionItemEditor,
            'P I': self.radioButton_Ngram_ProblemItemEditor,
            'I': self.radioButton_Ngram_ItemEditor,
            'U': self.radioButton_Ngram_UnknownEditor,
            'X': self.radioButton_Ngram_StopWordEditor,
            'P': self.radioButton_Ngram_ProblemEditor,
            'S': self.radioButton_Ngram_SolutionEditor,
            '': self.radioButton_Ngram_NotClassifiedEditor
        }

        self.buttonDictionary_NGram = {
            'Item': 'I',
            'Problem Item': 'P I',
            'Solution Item': 'S I',
            'Ambiguous (Unknown)': 'U',
            'Stop-word': 'X',
            'Problem': 'P',
            'Solution': 'S',
            'not yet classified': ''
        }

        self.buttonGroup_similarityPattern = QButtonGroup_similarityPattern(self.verticalLayout_1gram_SimilarityPattern)



        """
        Create the interaction on the MenuItems
        """
        self.actionNew_Project.triggered.connect(self.setMenu_projectNew)
        self.actionOpen_Project.triggered.connect(self.setMenu_projectOpen)
        self.actionProject_Settings.triggered.connect(self.setMenu_settings)
        self.actionSave_Project.triggered.connect(self.setMenu_projectSave)
        self.actionMap_CSV.triggered.connect(self.setMenu_mapCsvHeader)

        self.actionConnect.triggered.connect(self.setMenu_databaseConnect)
        self.actionRun_Query.triggered.connect(self.setMenu_databaseRunQuery)
        self.actionOpen_Database.triggered.connect(self.setMenu_databaseOpenBrowser)

        self.action_AutoPopulate_FromDatabase_1gramVocab.triggered.connect(self.setMenu_autopopulateFromDatabase_1gVocab)
        self.action_AutoPopulate_FromDatabase_NgramVocab.triggered.connect(self.setMenu_autopopulateFromDatabase_NgVocab)
        self.action_AutoPopulate_FromCSV_1gramVocab.triggered.connect(self.setMenu_autopopulateFromCSV_1gVocab)
        self.action_AutoPopulate_FromCSV_NgramVocab.triggered.connect(self.setMenu_autopopulateFromCSV_NgVocab)
        self.actionFrom_AutoPopulate_From1gramVocab.triggered.connect(self.setMenu_autopopulateNgramFrom1gram)

        self.actionTo_Zip.triggered.connect(self.setMenu_ExportZip)
        self.actionTo_Tar.triggered.connect(self.setMenu_ExportTar)
        self.actionImport.triggered.connect(self.setMenu_Import)


        self.tableWidget_1gram_TagContainer.itemSelectionChanged.connect(self.onSelect_tableViewItems1gramVocab)
        self.tableWidget_Ngram_TagContainer.itemSelectionChanged.connect(self.onSelect_tableViewItemsNgramVocab)

        self.buttonGroup_NGram_Classification.buttonClicked.connect(self.setAliasFromNgramButton)
        self.horizontalSlider_1gram_FindingThreshold.sliderMoved.connect(self.onMoveSlider_similarPattern)
        self.horizontalSlider_1gram_FindingThreshold.sliderReleased.connect(self.onMoveSlider_similarPattern)
        self.pushButton_1gram_UpdateTokenProperty.clicked.connect(self.onClick_Update1GramVocab)
        self.pushButton_Ngram_UpdateTokenProperty.clicked.connect(self.onClick_UpdateNGramVocab)

        self.pushButton_report_saveTrack.clicked.connect(self.onClick_saveTrack)
        self.pushButton_report_saveNewCsv.clicked.connect(self.onClick_saveNewCsv)
        self.pushButton_report_saveH5.clicked.connect(self.onClick_saveTagsHDFS)

        self.dialogTOU = DialogMenu_TermsOfUse()
        self.actionAbout_TagTool.triggered.connect(self.dialogTOU.show)

        self.tabWidget.currentChanged.connect(self.onChange_tableView)

        """
        Set the shortcut 
        """
        Qw.QShortcut(QtGui.QKeySequence("Ctrl+N"), self).activated.connect(self.setMenu_projectNew)
        self.actionNew_Project.setText(self.actionNew_Project.text() + "\tCtrl+N")
        Qw.QShortcut(QtGui.QKeySequence("Ctrl+S"), self).activated.connect(self.setMenu_projectSave)
        self.actionSave_Project.setText(self.actionSave_Project.text() + "\tCtrl+S")
        Qw.QShortcut(QtGui.QKeySequence("Ctrl+O"), self).activated.connect(self.setMenu_projectOpen)
        self.actionOpen_Project.setText(self.actionOpen_Project.text() + "\tCtrl+O")
        Qw.QShortcut(QtGui.QKeySequence("Ctrl+D"), self).activated.connect(self.setMenu_databaseConnect)
        self.actionConnect.setText(self.actionConnect.text() + "\tCtrl+D")

        self.show()

    def setMenu_projectNew(self):
        """
        When click on the New Project menu
        :return:
        """

        dialogMenu_newProject = DialogMenu_newProject(self.iconPath)
        self.setEnabled(False)
        dialogMenu_newProject.closeEvent = self.close_Dialog


        def onclick_ok():
            self.config = None
            self.config = self.config_default.copy()
            name, author, description, vocab1g, vocabNg, pathCSV_old = dialogMenu_newProject.get_data()

            if name and pathCSV_old:
                dialogMenu_newProject.lineEdit_NewProject_ProjectName.setStyleSheet(self.changeColor['default'])
                dialogMenu_newProject.lineEdit_NewProject_LoadCSV.setStyleSheet(self.changeColor['default'])
                if name not in self.existingProject:
                    dialogMenu_newProject.lineEdit_NewProject_ProjectName.setStyleSheet(self.changeColor['default'])
                    dialogMenu_newProject.close()

                    pathCSV_new = self.projectsPath / name
                    pathCSV_new.mkdir(parents=True, exist_ok=True)

                    pathCSV_old = Path(pathCSV_old)
                    self.set_config(name = name,
                                    author=author,
                                    description=description,
                                    vocab1g=vocab1g,
                                    vocabNg=vocabNg,
                                    original=pathCSV_old.name)


                    # create the projectfolder
                    pathCSV_new = self.projectsPath / name
                    pathCSV_new.mkdir(parents=True, exist_ok=True)

                    # open the dataframe and save is as utf8 on the project localisation
                    dataframe_tmp = openDataframe(pathCSV_old)
                    dataframe_tmp.to_csv(pathCSV_new/self.config['original'],encoding='utf-8-sig')

                    self.dataframe_Original = dataframe_tmp

                    self.setMenu_mapCsvHeader()

                else:
                    dialogMenu_newProject.lineEdit_NewProject_ProjectName.setStyleSheet(self.changeColor['wrongInput'])

            else:
                dialogMenu_newProject.lineEdit_NewProject_ProjectName.setStyleSheet(self.changeColor['wrongInput'])
                dialogMenu_newProject.lineEdit_NewProject_LoadCSV.setStyleSheet(self.changeColor['wrongInput'])

        dialogMenu_newProject.buttonBox__NewProject.accepted.connect(onclick_ok)

    def setMenu_projectOpen(self):
        """
        When click on the Load Project menu
        :return:
        """

        dialogMenu_openProject = DialogMenu_openProject(self.iconPath, self.projectsPath, self.existingProject)
        self.setEnabled(False)
        dialogMenu_openProject.closeEvent = self.close_Dialog

        def onclick_ok():
            if dialogMenu_openProject.comboBox_OpenProject_ProjectName.currentText():
                self.config = dialogMenu_openProject.get_data()
                self.whenProjectOpen()
                dialogMenu_openProject.close()


        def onclick_remove():
            if dialogMenu_openProject.comboBox_OpenProject_ProjectName.currentText() != "":
                choice = Qw.QMessageBox.question(self, 'Remove Project',
                                                 'Do you really want to remove the project?',
                                                 Qw.QMessageBox.Yes | Qw.QMessageBox.No, Qw.QMessageBox.No)

                if choice == Qw.QMessageBox.Yes:
                    def remove_folderContent(folder):
                        for file in folder.iterdir():
                            if file.is_file():
                                file.unlink()
                            elif file.is_dir:
                                remove_folderContent(file)
                        folder.rmdir()

                    remove_folderContent(self.projectsPath / dialogMenu_openProject.comboBox_OpenProject_ProjectName.currentText())
                    self.existingProject.remove(dialogMenu_openProject.comboBox_OpenProject_ProjectName.currentText())
                    dialogMenu_openProject.comboBox_OpenProject_ProjectName.clear()
                    dialogMenu_openProject.comboBox_OpenProject_ProjectName.addItems(self.existingProject)

                else:
                    print("NOTHING --> We did not remove your project")

        dialogMenu_openProject.pushButton_OpenProject_ProjectRemove.clicked.connect(onclick_remove)
        dialogMenu_openProject.buttonBox_OpenProject.accepted.connect(onclick_ok)

    def setMenu_projectSave(self):
        """
        Whan saving the project
        :return:
        """
        projectName= self.config.get('name')

        if projectName:
            saveYAMLConfig_File(self.projectsPath / self.config.get('name') / "config.yaml", self.config)

            folderPath = self.projectsPath / projectName
            folderPath.mkdir(parents=True, exist_ok=True)

            #TODO if can save file
            if self.dataframe_vocab1Gram is not None:
                vocab1gPath = self.config.get('vocab1g', 'vocab1g') + ".csv"
                vocab1gPath = folderPath / vocab1gPath
                self.dataframe_vocab1Gram.to_csv(vocab1gPath, encoding='utf-8-sig')

                vocabNgPath = self.config.get('vocabNg', 'vocabNg') + ".csv"
                vocabNgPath = folderPath / vocabNgPath
                self.dataframe_vocabNGram.to_csv(vocabNgPath, encoding='utf-8-sig')

            self.existingProject.add(projectName)

    def setMenu_databaseConnect(self):
        """
        when click on the connect to database menu
        :return:
        """
        dialogMenu_databaseConnect = DialogMenu_DatabaseConnect(iconPath=self.iconPath,
                                                                configDatabase = self.config.get('database',{})
                                                                )
        self.setEnabled(False)
        dialogMenu_databaseConnect.closeEvent = self.close_Dialog

        def onclick_ok():
            username, schema, server, serverport, browserport, password = dialogMenu_databaseConnect.get_data()

            schematmp = openYAMLConfig_File(Path(schema))
            try:
                self.set_config(username=username,
                                schema=schema,
                                server=server,
                                serverport=serverport,
                                browserport=browserport
                                )

                self.database = DatabaseNeo4J(user=username,
                                         password=password,
                                         server=server,
                                         portBolt=serverport,
                                         portUi=browserport,
                                         schema=schematmp)

                dialogMenu_databaseConnect.close()

                self.enableFeature(existDatabase=True)

            except neo4j.exceptions.AuthError:
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_Username.setStyleSheet(self.changeColor['wrongInput'])
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_Password.setStyleSheet(self.changeColor['wrongInput'])
            except (neo4j.exceptions.AddressError, neo4j.exceptions.ServiceUnavailable):
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_ServerPortNumber.setStyleSheet(self.changeColor['wrongInput'])
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_ServerName.setStyleSheet(self.changeColor['wrongInput'])
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_Username.setStyleSheet(self.changeColor['default'])
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_Password.setStyleSheet(self.changeColor['default'])
            except FileNotFoundError:
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_OpenSchema.setStyleSheet(self.changeColor['wrongInput'])
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_ServerPortNumber.setStyleSheet(self.changeColor['wrongInput'])
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_ServerName.setStyleSheet(self.changeColor['default'])
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_Username.setStyleSheet(self.changeColor['default'])
                dialogMenu_databaseConnect.lineEdit_DialogDatabaseConnection_Password.setStyleSheet(self.changeColor['default'])


        dialogMenu_databaseConnect.buttonBox_DialogDatabaseConnection.accepted.connect(onclick_ok)

    def setMenu_databaseRunQuery(self):
        """
        When click on the run Query menu
        :return:
        """

        dialogMenu_databaseRunQuery = DialogMenu_DatabaseRunQueries(iconPath = self.iconPath,
                                                                    database = self.database,
                                                                    dataframe_Original = self.dataframe_Original,
                                                                    dataframe_vocab1Gram= self.dataframe_vocab1Gram,
                                                                    dataframe_vocabNGram= self.dataframe_vocabNGram,
                                                                    bin1g_df=self.tag_df,
                                                                    binNg_df=self.relation_df,
                                                                    vocab1g_df=self.dataframe_vocab1Gram,
                                                                    vocabNg_df= self.dataframe_vocabNGram,
                                                                    csvHeaderMapping= self.config['csvinfo'].get('mapping',{}),
                                                                    databaseToCsv_mapping= self.databaseToCsv_mapping.copy()
                                                                    )

        self.setEnabled(False)
        dialogMenu_databaseRunQuery.closeEvent = self.close_Dialog

        def onclick_ok():
            dialogMenu_databaseRunQuery.runQueries()
            dialogMenu_databaseRunQuery.close()

        dialogMenu_databaseRunQuery.button_DialogDatabaseRunQuery.accepted.connect(onclick_ok)

    def setMenu_databaseOpenBrowser(self):
        """
        When click on open browser
        :return:
        """
        webbrowser.open(self.database.url, new=1)

    def setMenu_autopopulateFromDatabase_1gVocab(self):

        done, result = self.database.getTokenTagClassification()

        if done:
            df = resultToObservationDataframe(result).set_index("tokens")
            self.dataframe_vocab1Gram.replace('', np.nan, inplace=True)

            mask = self.dataframe_vocab1Gram[["NE", "alias"]].isnull().all(axis=1)

            df_tmp = self.dataframe_vocab1Gram.loc[mask, :]
            df_tmp.update(other=df, overwrite=False)

            self.dataframe_vocab1Gram.update(df_tmp, overwrite=False)
            self.dataframe_vocab1Gram.fillna('', inplace=True)

            self.printDataframe_TableviewProgressBar(dataframe=self.dataframe_vocab1Gram,
                                                     tableview= self.tableWidget_1gram_TagContainer,
                                                     progressBar=self.progressBar_1gram_TagComplete)

    def setMenu_autopopulateFromDatabase_NgVocab(self):

        done, result = self.database.getTokenTagClassification()

        if done:
            df = resultToObservationDataframe(result).set_index("tokens")

            self.dataframe_vocabNGram.replace('', np.nan, inplace=True)

            mask = self.dataframe_vocabNGram[["NE", "alias"]].isnull().all(axis=1)

            df_tmp = self.dataframe_vocabNGram.loc[mask, :]
            df_tmp.update(other=df, overwrite=False)

            self.dataframe_vocabNGram.update(df_tmp, overwrite=False)
            self.dataframe_vocabNGram.fillna('', inplace=True)

            self.printDataframe_TableviewProgressBar(dataframe=self.dataframe_vocabNGram,
                                                     tableview=self.tableWidget_Ngram_TagContainer,
                                                     progressBar=self.progressBar_Ngram_TagComplete)

    def setMenu_autopopulateFromCSV_1gVocab(self):
        options = Qw.QFileDialog.Options()
        fileName, _ = Qw.QFileDialog.getOpenFileName(self,
                                                     self.objectName(), "Open NESTOR generated vocab File",
                                                     "csv Files (*.csv)", options=options)

        if fileName:

            df = pd.read_csv(fileName)[["tokens","NE","alias"]].set_index("tokens")

            self.dataframe_vocab1Gram.replace('', np.nan, inplace=True)

            mask = self.dataframe_vocab1Gram[["NE", "alias"]].isnull().all(axis=1)

            df_tmp = self.dataframe_vocab1Gram.loc[mask, :]
            df_tmp.update(other=df, overwrite=False)

            self.dataframe_vocab1Gram.update(df_tmp, overwrite=False)
            self.dataframe_vocab1Gram.fillna('', inplace=True)

            self.printDataframe_TableviewProgressBar(dataframe =self.dataframe_vocab1Gram,
                                                     tableview = self.tableWidget_1gram_TagContainer,
                                                     progressBar = self.progressBar_1gram_TagComplete)

    def setMenu_autopopulateFromCSV_NgVocab(self):

        options = Qw.QFileDialog.Options()
        fileName, _ = Qw.QFileDialog.getOpenFileName(self,
                                                     self.objectName(), "Open NESTOR generated vocab File",
                                                     "csv Files (*.csv)", options=options)

        if fileName:
            df = pd.read_csv(fileName)[["tokens", "NE", "alias"]].set_index("tokens")

            self.dataframe_vocabNGram.replace('', np.nan, inplace=True)

            mask = self.dataframe_vocabNGram[["NE", "alias"]].isnull().all(axis=1)

            df_tmp = self.dataframe_vocabNGram.loc[mask, :]
            df_tmp.update(other=df, overwrite=False)

            self.dataframe_vocabNGram.update(df_tmp, overwrite=False)
            self.dataframe_vocabNGram.fillna('', inplace=True)

            self.printDataframe_TableviewProgressBar(dataframe=self.dataframe_vocabNGram,
                                                     tableview=self.tableWidget_Ngram_TagContainer,
                                                     progressBar=self.progressBar_Ngram_TagComplete)

    def setMenu_autopopulateNgramFrom1gram(self):

        self.extract_NgVocab(init= self.dataframe_vocabNGram)

        self.printDataframe_TableviewProgressBar(dataframe=self.dataframe_vocabNGram,
                                                 tableview=self.tableWidget_Ngram_TagContainer,
                                                 progressBar=self.progressBar_Ngram_TagComplete)

        print('Done --> Updated Ngram classification from 1-gram vocabulary!')

    def setMenu_settings(self):
        """
        When click on the Settings menu
        """

        dialogMenu_settings = DialogMenu_settings(name = self.config.get('name',''),
                                                  author = self.config.get('author',''),
                                                  description = self.config.get('description',''),
                                                  vocab1g = self.config.get('vocab1g',''),
                                                  vocabNg = self.config.get('vocabNg',''),
                                                  configSettings = self.config.get('settings'),
                                                  untracked = "; ".join(self.config['csvinfo'].get('untracked_token', "")),
                                                  iconPath=self.iconPath
                                                  )
        self.setEnabled(False)
        dialogMenu_settings.closeEvent = self.close_Dialog

        def onclick_ok():
            name, author, description, vocab1g, vocabNg, numberTokens, alreadyChecked_threshold, showCkeckBox_threshold, untrackedTokenList = dialogMenu_settings.get_data()

            if name:
                dialogMenu_settings.lineEdit_Settings_ProjectName.setStyleSheet(self.changeColor['default'])
                oldPath = self.projectsPath / self.config.get('name')
                oldPath.rename(self.projectsPath / name)
                #TODO same as above but for the vocabfile name

                self.existingProject.remove(self.config['name'])
                self.existingProject.add(name)


                self.set_config(name=name,
                                author= author,
                                description= description,
                                vocab1g=vocab1g,
                                vocabNg=vocabNg,
                                numberTokens=numberTokens,
                                alreadyChecked_threshold=alreadyChecked_threshold,
                                showCkeckBox_threshold=showCkeckBox_threshold,
                                untrackedTokenList=untrackedTokenList)
                dialogMenu_settings.close()
                self.buttonGroup_similarityPattern = QButtonGroup_similarityPattern(self.verticalLayout_1gram_SimilarityPattern)

            else:
                dialogMenu_settings.lineEdit_Settings_ProjectName.setStyleSheet(self.changeColor['wrongInput'])

        dialogMenu_settings.buttonBox_Setup.accepted.connect(onclick_ok)

    def setMenu_mapCsvHeader(self):
        """
        When select the NLP collumn and mapping the csv to the database
        :return:
        """

        databaseToCsv_list = []
        for key1 ,value1 in self.databaseToCsv_mapping.items():
            for key2, value2 in value1.items():
                databaseToCsv_list.append(value2)

        #TODO AttributeError: 'NoneType' object has no attribute 'columns'
        self.dialogMenu_csvHeaderMapping = DialogMenu_csvHeaderMapping(csvHeaderContent= list(self.dataframe_Original.columns.values),
                                                                  mappingContent= databaseToCsv_list,
                                                                  configCsvHeader = self.config['csvinfo'].get('nlpheader', []),
                                                                  configMapping = self.config['csvinfo'].get('mapping', {}))

        self.setEnabled(False)
        self.dialogMenu_csvHeaderMapping.closeEvent = self.close_Dialog

        def onclick_ok():
            nlpHeader, csvMapping = self.dialogMenu_csvHeaderMapping.get_data()
            if nlpHeader:
                self.set_config(nlpHeader=nlpHeader, csvMapping=csvMapping)
                self.dialogMenu_csvHeaderMapping.close()

                self.whenProjectOpen()

        self.dialogMenu_csvHeaderMapping.buttonBox_csvHeaderMapping.accepted.connect(onclick_ok)

    def setMenu_ExportZip(self, format):
        """
        save the current project to a format zip file
        :param format:
        :return:
        """
        target = str(Qw.QFileDialog.getExistingDirectory(self, "Select Directory"))

        if target:
            target = str(Path(target) / self.config.get('name', 'noName'))
            current = str(self.projectsPath / self.config.get('name'))

            shutil.make_archive(target, 'zip', current)

    def setMenu_ExportTar(self, format):
        """
        save the current project to a format tar file
        :param format:
        :return:
        """
        target = str(Qw.QFileDialog.getExistingDirectory(self, "Select Directory"))

        if target:
            target = str(Path(target) / self.config.get('name', 'noName'))
            current = str(self.projectsPath / self.config.get('name'))

            shutil.make_archive(target, 'tar', current)

    def setMenu_Import(self):
        """
        Import a zip or a tar project
        :return:
        """
        fileName, _ = Qw.QFileDialog.getOpenFileName(self, "", "Select file to import",
                                                     'zip and tar files (*.zip *.tar)')
        if fileName:
            fileName = Path(fileName)
            self.projectsPath = self.projectsPath/ fileName.name[:-4]
            shutil.unpack_archive(str(fileName), str(self.projectsPath))

            self.existingProject.add(fileName.name[:-4])

            self.config=openYAMLConfig_File(folder/'config.yaml')

            self.whenProjectOpen()

    def printDataframe_TableviewProgressBar(self, dataframe, tableview, progressBar):
        """
        print the given dataframe onto the given tableview
        :param dataframe:
        :param tableview:
        :return:
        """
        if dataframe is not None:
            temp_df = dataframe.reset_index()
            nbrows, nbcols = temp_df.shape
            tableview.setColumnCount(nbcols - 1)  # ignore score column
            print([nbrows, self.config['settings'].get('numberTokens', 1000)])
            tableview.setRowCount(min([nbrows, self.config['settings'].get('numberTokens', 1000)]))
            for i in range(tableview.rowCount()):
                for j in range(nbcols - 1):  # ignore score column
                    tableview.setItem(i, j, Qw.QTableWidgetItem(str(temp_df.iat[i, j])))
            try:
                for index in tableview.userUpdate:
                    if index < 1000:
                        tableview.item(index, 0).setBackground(Qg.QColor(77, 255, 184))

            except AttributeError:
                pass

            tableview.resizeColumnsToContents()
            tableview.resizeRowsToContents()
            tableview.setHorizontalHeaderLabels(temp_df.columns.tolist()[:-1])  # ignore score column
            tableview.setSelectionBehavior(Qw.QTableWidget.SelectRows)

            self.update_progress_bar(progressBar, dataframe)
        else:
            tableview.clearSpans()
            progressBar.setValue(0)

    def onSelect_tableViewItems1gramVocab(self):
        """
        When a given item is selected on the 1Gram TableView
        :return:
        """
        items = self.tableWidget_1gram_TagContainer.selectedItems()  # selected row
        token, classification, alias, notes = (str(i.text()) for i in items)

        if alias:
            self.lineEdit_1gram_AliasEditor.setText(alias)
        else:
            self.lineEdit_1gram_AliasEditor.setText(token)
        self.textEdit_1gram_NoteEditor.setText(notes)
        self.classificationDictionary_1Gram.get(classification, self.radioButton_1gram_NotClassifiedEditor).setChecked(True)


        self.buttonGroup_similarityPattern.textAlreadySelected = set()
        self.buttonGroup_similarityPattern.textToUncheck = set()
        self.buttonGroup_similarityPattern.create_checkBoxs(dataframe=self.dataframe_vocab1Gram,
                                                            token=token,
                                                            autoCheck_value=self.config['settings'].get('alreadyChecked_threshold', 50),
                                                            checkBox_show = self.horizontalSlider_1gram_FindingThreshold.value())

    def onMoveSlider_similarPattern(self):
        """
        When the slider on the buttom of the 1Gram is moved
        :return:
        """
        self.buttonGroup_similarityPattern.create_checkBoxs(dataframe=self.dataframe_vocab1Gram,
                                                            token=self.tableWidget_1gram_TagContainer.selectedItems()[0].text(),
                                                            autoCheck_value=self.config['settings'].get('alreadyChecked_threshold', 50),
                                                            checkBox_show= self.horizontalSlider_1gram_FindingThreshold.value())

    def onSelect_tableViewItemsNgramVocab(self):
        """
        When a given item is selected on the Ngram TableView
        :return:
        """
        items = self.tableWidget_Ngram_TagContainer.selectedItems()  # selected row
        token, classification, alias, notes = (str(i.text()) for i in items)



        if not alias:
            alias = token
            if classification == "I":
                alias = "_".join(alias.split(" "))

        self.lineEdit_Ngram_AliasEditor.setText(alias)

        self.textEdit_Ngram_NoteEditor.setText(notes)
        self.classificationDictionary_NGram.get(classification, self.radioButton_Ngram_NotClassifiedEditor).setChecked(True)



        # Take care of the layout in the middle.

        while self.gridLayout_Ngram_NGramComposedof.count():
            item = self.gridLayout_Ngram_NGramComposedof.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        xPos = 0
        yLabel = 0
        yValue = 1

        for tok1g in token.split(" "):

            # creat the NE, alias, notes

            firstToken = self.dataframe_vocab1Gram.loc[self.dataframe_vocab1Gram['alias'] == tok1g].iloc[0]
            for label, value in firstToken[:-1].iteritems():
                labelLabel = Qw.QLabel()
                labelLabel.setText(str(label)+":")
                labelLabel.setObjectName("labelNGramComposition" + str(label))
                self.gridLayout_Ngram_NGramComposedof.addWidget(labelLabel, xPos, yLabel)

                labelValue = Qw.QLabel()
                labelValue.setText(str(value))
                labelValue.setObjectName("labelNGramComposition" + str(value))
                self.gridLayout_Ngram_NGramComposedof.addWidget(labelValue, xPos, yValue)

                xPos += 1

            #creat the token list
            labelLabel = Qw.QLabel()
            labelLabel.setText('tokens :')
            labelLabel.setObjectName("labelNGramComposition" + 'alias')
            self.gridLayout_Ngram_NGramComposedof.addWidget(labelLabel, xPos, yLabel)

            similarityList = "\n".join(self.dataframe_vocab1Gram.index[self.dataframe_vocab1Gram['alias'] == tok1g].tolist())

            labelValueSimilarity = Qw.QLabel()
            labelValueSimilarity.setText(similarityList)
            labelValueSimilarity.setObjectName("labelNGramComposition" + 'aliasValue')
            self.gridLayout_Ngram_NGramComposedof.addWidget(labelValueSimilarity, xPos, yValue)

            xPos += 1

            separator = Qw.QFrame()
            separator.setFrameShape(Qw.QFrame.HLine)
            separator.setFrameShadow(Qw.QFrame.Sunken)
            separator.setObjectName("separator" + tok1g)
            self.gridLayout_Ngram_NGramComposedof.addWidget(separator, xPos, yLabel)

            xPos += 1

        verticalSpacer = Qw.QSpacerItem(20, 40, Qw.QSizePolicy.Minimum, Qw.QSizePolicy.Expanding)
        self.gridLayout_Ngram_NGramComposedof.addItem(verticalSpacer)

    def onClick_Update1GramVocab(self):
        """
        update the dataframe when update the 1Gram
        :return:
        """
        try:
            items = self.tableWidget_1gram_TagContainer.selectedItems()  # selected row
            token, classification, alias, notes = (str(i.text()) for i in items)


            for btn in self.buttonGroup_similarityPattern.buttons():
                if btn.isChecked():
                    new_alias = self.buttonDictionary_1Gram.get(self.buttonGroup_1Gram_Classification.checkedButton().text(), '')

                    self.dataframe_vocab1Gram.at[btn.text(), 'alias'] =  self.lineEdit_1gram_AliasEditor.text()
                    self.dataframe_vocab1Gram.at[btn.text(), 'notes'] = self.textEdit_1gram_NoteEditor.toPlainText()
                    self.dataframe_vocab1Gram.at[btn.text(), 'NE'] = new_alias

            # remove the information for the token that WAS the same but the user did not want it to be the same anymore
            # only if they had the same alias
            for textToUncheck in self.buttonGroup_similarityPattern.textToUncheck:
                if self.dataframe_vocab1Gram.at[textToUncheck,"alias"] == alias:
                    self.dataframe_vocab1Gram.at[textToUncheck, 'alias'] = ""
                    self.dataframe_vocab1Gram.at[textToUncheck, 'notes'] = ""
                    self.dataframe_vocab1Gram.at[textToUncheck, 'NE'] = ""


            self.printDataframe_TableviewProgressBar(dataframe= self.dataframe_vocab1Gram,
                                                     tableview=self.tableWidget_1gram_TagContainer,
                                                     progressBar=self.progressBar_1gram_TagComplete)

            self.tableWidget_1gram_TagContainer.selectRow(self.tableWidget_1gram_TagContainer.currentRow() + 1)

        except (IndexError, ValueError):
            Qw.QMessageBox.about(self, 'Can\'t select', "You should select a row first")

    def onClick_UpdateNGramVocab(self):

        items = self.tableWidget_Ngram_TagContainer.selectedItems()  # selected row
        token, classification, alias, notes = (str(i.text()) for i in items)

        self.dataframe_vocabNGram.at[token, 'alias'] = self.lineEdit_Ngram_AliasEditor.text()
        self.dataframe_vocabNGram.at[token, 'notes'] = self.textEdit_Ngram_NoteEditor.toPlainText()
        self.dataframe_vocabNGram.at[token, 'NE'] = self.buttonDictionary_NGram.get(self.buttonGroup_NGram_Classification.checkedButton().text(), '')

        if self.buttonDictionary_NGram.get(self.buttonGroup_NGram_Classification.checkedButton().text(), '') == "I":
            self.dataframe_vocabNGram.at[token, 'alias'] = "_".join(self.lineEdit_Ngram_AliasEditor.text().split(" "))

        self.printDataframe_TableviewProgressBar(dataframe=self.dataframe_vocabNGram,
                                                 tableview=self.tableWidget_Ngram_TagContainer,
                                                 progressBar=self.progressBar_Ngram_TagComplete)
        self.tableWidget_Ngram_TagContainer.selectRow(self.tableWidget_Ngram_TagContainer.currentRow() + 1)

    def set_config(self, name=None, author=None, description=None, vocab1g=None, vocabNg=None, original=None,
                   numberTokens=None, alreadyChecked_threshold=None, showCkeckBox_threshold=None, untrackedTokenList=None,
                   username = None, schema = None, server = None, serverport = None, browserport = None,
                   nlpHeader = None, csvMapping=None):
        """
        When changing an information that needs to be saved in the config file
        It Reload all the printing and stuff
        :param name:
        :param author:
        :param description:
        :param vocab1g:
        :param vocabNg:
        :param original:
        :param numberTokens:
        :param alreadyChecked_threshold:
        :param showCkeckBox_threshold:
        :return:
        """

        if name:
            self.config["name"] = name
        if author:
            self.config["author"] = author
        if description:
            self.config["description"] = description
        if vocab1g:
            self.config["vocab1g"] = vocab1g
        if vocabNg:
            self.config["vocabNg"] = vocabNg
        if original:
            self.config["original"] = original

        if numberTokens:
            self.config['settings']["numberTokens"] = numberTokens
        if alreadyChecked_threshold:
            self.config['settings']["alreadyChecked_threshold"] = alreadyChecked_threshold
        if showCkeckBox_threshold:
            self.config['settings']["showCkeckBox_threshold"] = showCkeckBox_threshold

        if untrackedTokenList:
            self.config['csvinfo']["untracked_token"] = untrackedTokenList
        if nlpHeader:
            self.config['csvinfo']["nlpheader"] = nlpHeader
        if csvMapping:
            self.config['csvinfo']["mapping"] = csvMapping

        if username:
            self.config['database']["username"] =username
        if schema:
            self.config['database']["schema"] =schema
        if server:
            self.config['database']["server"] =server
        if serverport:
            self.config['database']["serverport"] =serverport
        if browserport:
            self.config['database']["browserport"] =browserport

        saveYAMLConfig_File(self.projectsPath / self.config.get('name') / "config.yaml", self.config)

    def onChange_tableView(self, tabindex):
        """
        when changing the tab
        :param tabindex:
        :return:
        """
        #1gramtab
        if tabindex == 0:
            pass

        #ngramtab
        elif tabindex == 1:
            self.extract_NgVocab(init=self.dataframe_vocabNGram)

        #reporttab
        elif tabindex == 2:
            pass

    def whenProjectOpen(self):
        """
        This function will execute all the changes when you create / open / import a new project
        self.config needs to be updated with the new project
        :return:
        """


        self.existingProject.add(self.config.get('name',""))

        #reset all the value to default
        self.dataframe_Original = None
        self.dataframe_vocab1Gram = None
        self.dataframe_vocabNGram = None
        self.dataframe_completeness = None
        self.tokenExtractor_1Gram = kex.TokenExtractor()  # sklearn-style TF-IDF calc
        self.tokenExtractor_nGram = kex.TokenExtractor(ngram_range=(2, 2))
        self.clean_rawText_1Gram = None
        self.clean_rawText = None
        self.tag_df = None
        self.relation_df = None
        self.tag_readable = None
        self.dataframe_completeness = None
        self.dataframe_completeness=None

        self.printDataframe_TableviewProgressBar(dataframe=self.dataframe_vocab1Gram,
                                                 tableview=self.tableWidget_1gram_TagContainer,
                                                 progressBar=self.progressBar_1gram_TagComplete)
        self.printDataframe_TableviewProgressBar(dataframe=self.dataframe_vocabNGram,
                                                 tableview=self.tableWidget_Ngram_TagContainer,
                                                 progressBar=self.progressBar_Ngram_TagComplete)

        #self.config = self.config_default.copy()

        #Open dataframs
        self.dataframe_Original = openDataframe(self.projectsPath / self.config['name'] / self.config['original'])

        vocname = str(self.config.get('vocab1g')) + '.csv'
        vocab1gPath = self.projectsPath / self.config.get('name') / vocname
        vocname = str(self.config.get('vocabNg')) + '.csv'
        vocabNgPath = self.projectsPath / self.config.get('name') / vocname


        # if we open a project, init the new dataframe with the one in the vocab
        if vocab1gPath.exists():
            self.extract_1gVocab(vocab1gPath, openDataframe(vocab1gPath).fillna("").set_index("tokens"))
        #if new project, just create the dataframe
        else:
            self.extract_1gVocab(vocab1gPath)

        if vocabNgPath.exists():
            self.extract_NgVocab(init =openDataframe(vocabNgPath).fillna("").set_index("tokens"))
        else:
            self.extract_NgVocab(vocabNgPath =vocabNgPath)

        self.printDataframe_TableviewProgressBar(dataframe=self.dataframe_vocab1Gram,
                                                 tableview=self.tableWidget_1gram_TagContainer,
                                                 progressBar=self.progressBar_1gram_TagComplete)
        self.printDataframe_TableviewProgressBar(dataframe=self.dataframe_vocabNGram,
                                                 tableview=self.tableWidget_Ngram_TagContainer,
                                                 progressBar=self.progressBar_Ngram_TagComplete)

        self.horizontalSlider_1gram_FindingThreshold.setValue(self.config['settings'].get('showCkeckBox_threshold',50))

        # make menu available
        self.enableFeature(existProject=True, existTagExtracted=False)

    def extract_1gVocab(self, vocab1gPath= None,  init=None):
        """
        create the 1Gvocab from the original dataframe
        :return:
        """
        columns = self.config['csvinfo'].get('nlpheader', 0)
        special_replace = self.config['csvinfo'].get('untracked_token', None)
        print(special_replace)
        nlp_selector = kex.NLPSelect(columns=columns, special_replace=special_replace)

        self.clean_rawText = nlp_selector.transform(self.dataframe_Original)  # might not need to set it as self

        list_tokenExtracted = self.tokenExtractor_1Gram.fit_transform(self.clean_rawText)

        self.dataframe_vocab1Gram = kex.generate_vocabulary_df(self.tokenExtractor_1Gram, filename=vocab1gPath, init=init)

        self.dataframe_vocab1Gram.to_csv(vocab1gPath, encoding='utf-8-sig')

    def extract_NgVocab(self, vocabNgPath=None, init=None):
        """
        Create the Ngram Vocab from the 1G vocab and the original dataframe
        :return:
        """
        self.clean_rawText_1Gram = kex.token_to_alias(self.clean_rawText, self.dataframe_vocab1Gram)

        list_tokenExtracted = self.tokenExtractor_nGram.fit_transform(self.clean_rawText_1Gram)

        # create the n gram dataframe

        self.dataframe_vocabNGram = kex.generate_vocabulary_df(self.tokenExtractor_nGram, filename=vocabNgPath, init=init)

        NE_types = self.config['classification'].get("type")
        NE_map_rules = self.config['classification'].get('mapping')
        self.dataframe_vocabNGram = kex.ngram_automatch(self.dataframe_vocab1Gram, self.dataframe_vocabNGram, NE_types, NE_map_rules)

    def update_progress_bar(self, progressBar, dataframe):
        """set the value of the progress bar based on the dataframe score

        Parameters
        ----------
        progressBar :

        dataframe :


        Returns
        -------

        """
        scores = dataframe['score']
        matched = scores[dataframe['NE'] != '']
        completed_pct = matched.sum() / scores.sum()
        progressBar.setValue(100 * completed_pct)

    def setAliasFromNgramButton(self, button):
        """
        When check a radio button on the Ngram button group, change the alias dependent on the classification
        :param button:
        :return:
        """
        if button == self.classificationDictionary_NGram.get("I"):
            alias = '_'.join(self.lineEdit_Ngram_AliasEditor.text().split(" "))
            self.lineEdit_Ngram_AliasEditor.setText(alias)
        else:
            alias = ' '.join(self.lineEdit_Ngram_AliasEditor.text().split("_"))
            self.lineEdit_Ngram_AliasEditor.setText(alias)

    def keyPressEvent(self, event):
        """listenr on the keyboard

        Parameters
        ----------
        e :
            return:
        event :


        Returns
        -------

        """

        if event.key() == Qt.Key_Return:
            if self.tabWidget.currentIndex() == 0:
                self.onClick_Update1GramVocab()
            elif self.tabWidget.currentIndex() ==1:
                self.onClick_UpdateNGramVocab()

    def close_Dialog(self, event):
        """
        When a window is closed (x, cancel, ok)
        :param event:
        :return:
        """
        self.setEnabled(True)

    def closeEvent(self, event):
        """
        Trigger when the user close the Tagging Tool Window
        :param event:
        :return:
        """
        choice = Qw.QMessageBox.question(self, 'Shut it Down',
                                         'Do you want to save your changes before closing?',
                                         Qw.QMessageBox.Save | Qw.QMessageBox.Close | Qw.QMessageBox.Cancel)

        if choice == Qw.QMessageBox.Save:
            print("SAVE AND CLOSE --> vocab 1gram and Ngram, as well as the config file")
            self.database.close()
            self.setMenu_projectSave()
        elif choice == Qw.QMessageBox.Cancel:
            print("NOTHING --> config file saved (in case)")
            event.ignore()
        else:
            print("CLOSE NESTOR --> we save your config file so it is easier to open it next time")
            self.database.close()

    def onClick_saveTrack(self):
        """save the current completness of the token in a dataframe
        :return:

        Parameters
        ----------

        Returns
        -------

        """
        #
        # # block any action on the main window
        #
        # # get the main wondow possition
        # rect = self.geometry()
        # rect.setHeight(70)
        # rect.setWidth(200)
        #
        # window_DialogWait = DialogWait(iconPath=self.iconPath)
        # window_DialogWait.setGeometry(rect)
        # # block the Dialog_wait in front of all other windows
        # window_DialogWait.show()
        # Qw.QApplication.processEvents()

        print("SAVE IN PROCESS --> calculating the extracted tags and statistics...")
        # do 1-grams
        print('ONE GRAMS...')
        tags_df = kex.tag_extractor(self.tokenExtractor_1Gram,
                                    self.clean_rawText,
                                    vocab_df=self.dataframe_vocab1Gram)
        # self.tags_read = kex._get_readable_tag_df(self.tags_df)
        #window_DialogWait.setProgress(30)
        #Qw.QApplication.processEvents()
        # do 2-grams
        print('TWO GRAMS...')
        tags2_df = kex.tag_extractor(self.tokenExtractor_nGram,
                                     self.clean_rawText_1Gram,
                                     vocab_df=self.dataframe_vocabNGram[self.dataframe_vocabNGram.alias.notna()])

        #window_DialogWait.setProgress(60)
        #Qw.QApplication.processEvents()
        # merge 1 and 2-grams.
        self.tag_df = tags_df.join(tags2_df.drop(axis='columns', labels=tags_df.columns.levels[1].tolist(), level=1))
        self.tag_readable = kex._get_readable_tag_df(self.tag_df)

        self.relation_df = self.tag_df.loc[:, ['P I', 'S I']]
        self.tag_df = self.tag_df.loc[:, ['I', 'P', 'S', 'U', 'NA']]
        # tag_readable.head(10)

        # do statistics
        tag_pct, tag_comp, tag_empt = kex.get_tag_completeness(self.tag_df)

        self.label_report_tagCompleteness.setText(f'Tag PPV: {tag_pct.mean():.2%} +/- {tag_pct.std():.2%}')
        self.label_report_completeDocs.setText(
            f'Complete Docs: {tag_comp} of {len(self.tag_df)}, or {tag_comp/len(self.tag_df):.2%}')
        self.label_report_emptyDocs.setText(
            f'Empty Docs: {tag_empt} of {len(self.tag_df)}, or {tag_empt/len(self.tag_df):.2%}')

        #window_DialogWait.setProgress(90)
        #Qw.QApplication.processEvents()
        self.completenessPlot._set_dataframe(tag_pct)
        nbins = int(np.percentile(self.tag_df.sum(axis=1), 90))
        print(f'Docs have at most {nbins} tokens (90th percentile)')
        self.completenessPlot.plot_it(nbins)

        self.dataframe_completeness = tag_pct
        #window_DialogWait.setProgress(99)
        #Qw.QApplication.processEvents()
        #window_DialogWait.close()


        #Qw.QApplication.processEvents()

        self.enableFeature(existTagExtracted=True)
        print("SAVE --> your information has been saved, you can now extract your result in CSV or HDF5")

    def onClick_saveNewCsv(self):
        """generate a new csv with the original csv and the generated token for the document
        :return:

        Parameters
        ----------

        Returns
        -------

        """
        if self.tag_readable is None:
            self.onClick_saveTrack()

        fname, _ = Qw.QFileDialog.getSaveFileName(self, 'Save File')
        if fname is not "":
            if fname[-4:] != '.csv':
                fname += '.csv'

            self.dataframe_Original.join(self.tag_readable, lsuffix="_pre").to_csv(fname)
            print('SAVE --> readable csv with tagged documents saved at: ', str(fname))

    def onClick_saveTagsHDFS(self):
        """generate a new csv with the document and the tag occurences (0 if not 1 if )
        :return:

        Parameters
        ----------

        Returns
        -------

        """

        if self.tag_df is None:
            self.onClick_saveTrack()
        fname, _ = Qw.QFileDialog.getSaveFileName(self, 'Save File')

        if fname is not "":
            if fname[-3:] != '.h5':
                fname += '.h5'

            col_map = self.config['csvinfo'].get('mapping', {})
            save_df = self.dataframe_Original[list(col_map.keys())]
            save_df = save_df.rename(columns=col_map)
            save_df.to_hdf(fname, key='df')

            self.tag_df.to_hdf(fname, key='tags')
            self.relation_df.to_hdf(fname, key='rels')
            print('SAVE --> HDF5 document containing:'
                  '\n\t- the original document (with updated header)'
                  '\n\t- the binary matrices of Tag'
                  '\n\t- the binary matrices of combined Tag')

    def enableFeature(self, existProject = None, existDatabase = None, existTagExtracted=None):
        #database exists
        if existDatabase is not None:
            if existDatabase is True:
                self.actionRun_Query.setEnabled(True)
                self.actionOpen_Database.setEnabled(True)
                self.menu_AutoPopulate_FromDatabase.setEnabled(True)
            elif existDatabase is False:
                self.actionRun_Query.setEnabled(False)
                self.actionOpen_Database.setEnabled(False)
                self.menu_AutoPopulate_FromDatabase.setEnabled(False)

        #if project exists
        if existProject is not None:
            if existProject is True:
                self.actionSave_Project.setEnabled(True)
                self.actionProject_Settings.setEnabled(True)
                self.actionMap_CSV.setEnabled(True)
                self.menuAuto_populate.setEnabled(True)
                self.menuExport.setEnabled(True)
                self.pushButton_report_saveTrack.setEnabled(True)
                self.tabWidget.setEnabled(True)
                self.menuDatabase.setEnabled(True)
            elif existProject is False:
                self.actionSave_Project.setEnabled(False)
                self.actionProject_Settings.setEnabled(False)
                self.actionMap_CSV.setEnabled(False)
                self.menuAuto_populate.setEnabled(False)
                self.menuExport.setEnabled(False)
                self.pushButton_report_saveTrack.setEnabled(False)
                self.tabWidget.setEnabled(False)
                self.menuDatabase.setEnabled(False)

        #if tag has been extracted
        if existTagExtracted is not None:
            if existTagExtracted is True:
                self.pushButton_report_saveNewCsv.setEnabled(True)
                self.pushButton_report_saveH5.setEnabled(True)
            elif existTagExtracted is False:
                self.pushButton_report_saveNewCsv.setEnabled(False)
                self.pushButton_report_saveH5.setEnabled(False)

def openYAMLConfig_File(yaml_path, dict={}):
    """open a Yaml file based on the given path
    :return: a dictionary

    Parameters
    ----------
    yaml_path :

    dict :
         (Default value = None)

    Returns
    -------

    """
    if yaml_path.is_file():
        with open(yaml_path, 'r') as yamlfile:
            config = yaml.load(yamlfile)
            print("OPEN --> YAML file at: ", yaml_path)
            if not config:
                config = {}
    else:
        config = dict
        with open(yaml_path, 'w') as yamlfile:
            pyaml.dump(config, yamlfile)
            print("CREATE --> YAML file at: ", yaml_path)
    return config

def saveYAMLConfig_File(yaml_path, dict):
    """save a Yaml file based on the given path
    :return: a dictionary

    Parameters
    ----------
    yaml_path :

    dict :


    Returns
    -------

    """


    with open(yaml_path, 'w') as yamlfile:
        pyaml.dump(dict, yamlfile)
        print("SAVE --> YAML file at: ", yaml_path)

def openDataframe(path):
    """set the dataframe for the window

    Parameters
    ----------
    dataframe_1Gram :
        param dataframe_NGram: (Default value = None)
    dataframe_NGram :
         (Default value = None)
    dataframe_Original :
         (Default value = None)

    Returns
    -------

    """

    try:
        return pd.read_csv(path)
    except UnicodeDecodeError:
        print("WAIT --> your file are not an UTF8 file, we are searching the good encoding")
        print("(you might want to open it and save it as UTF8 for the next time, it is way faster))")
        encoding = chardet.detect(open(path, 'rb').read())['encoding']
        return pd.read_csv(path, encoding=encoding)


class QButtonGroup_similarityPattern(Qw.QButtonGroup):
    def __init__(self, layout):
        Qw.QButtonGroup.__init__(self)
        self.setExclusive(False)
        self.layout = layout
        self.spacer = None
        self.textAlreadySelected = set()
        self.textToUncheck = set()

        self.buttonClicked.connect(self.set_textSelected)

    def set_textSelected(self, button):
        """
        store the selected button in a list
        :param button:
        :return:
        """
        if button.isChecked():
            self.textAlreadySelected.add(button.text())
            if button.text() in self.textToUncheck:
                self.textToUncheck.remove(button.text())
        else:
            self.textAlreadySelected.remove(button.text())
            self.textToUncheck.add(button.text())

    def create_checkBoxs(self, dataframe, token, autoCheck_value= 99, checkBox_show= 50):
        """create and print the checkboxes
        check it on condition

        Parameters
        ----------
        token_list :
            param autoMatch_score:
        autoMatch_score :

        dataframe :

        alias :


        Returns
        -------

        """
        self.clean_checkboxes()

        #get the similar tokne on the dataframe
        mask = dataframe.index.str[0] == token[0]
        similar = zz.extractBests(token, dataframe.index[mask],
                                  limit=20)[:int( checkBox_show * 20 / 100)]

        alias = dataframe.loc[token, 'alias']

        #for each one, create the checkbox
        for token, score in similar:
            btn = Qw.QCheckBox(token)
            self.addButton(btn)
            self.layout.addWidget(btn)

            # auto_checked the given chechbox
            if alias is '':
                if score >= autoCheck_value:
                    btn.setChecked(True)
                    self.textAlreadySelected.add(token)
            else:
                if dataframe.loc[btn.text(), 'alias'] == alias:
                    btn.setChecked(True)
                    self.textAlreadySelected.add(token)

            if token in self.textAlreadySelected:
                btn.setChecked(True)

        self.spacer = Qw.QSpacerItem(20, 40, Qw.QSizePolicy.Minimum, Qw.QSizePolicy.Expanding)
        self.layout.addSpacerItem(self.spacer)

    def clean_checkboxes(self):
        """remove all from the layout
        :return:

        Parameters
        ----------

        Returns
        -------

        """
        for btn in self.buttons():
            self.removeButton(btn)
            self.layout.removeWidget(btn)
            btn.deleteLater()
        self.layout.removeItem(self.spacer)


class MyMplCanvas(FigureCanvas):
    """the canvas used to print the plot in the right layout of the kpi UI
    All the characteristic in common for all the plot should be in this class

    Parameters
    ----------

    Returns
    -------

    """

    def __init__(self, layout=None, parent_layout=None, dataframe=None, width=4, height=3, dpi=100):
        self._set_dataframe(dataframe)
        self.layout = layout

        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)

        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent_layout)
        self.layout.addWidget(self, 0,0,1,1)

        # self.plot_it()

        FigureCanvas.setSizePolicy(self,Qw.QSizePolicy.Expanding, Qw.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

    def _set_dataframe(self, dataframe):
        """set the dataframe

        Parameters
        ----------
        dataframe :
            return:

        Returns
        -------

        """
        self.dataframe=dataframe

    def plot_it(self, nbins=10):
        """print the plot here we have the original plot
        :return:

        Parameters
        ----------

        Returns
        -------

        """
        self.axes.clear()
        if self.dataframe is not None:
            # with sns.axes_style('ticks') as style, \
            #         sns.plotting_context('poster') as context:
            sns.distplot(self.dataframe.dropna(),
                         bins=nbins,
                         kde_kws={'cut': 0},
                         hist_kws={'align': 'mid'},
                         kde=True,
                         ax=self.axes,
                         color='xkcd:slate')
            self.axes.set_xlim(0.1, 1.0)
            self.axes.set_xlabel('fraction of MWO tokens getting tagged')
            self.axes.set_title('Distribution over MWO\'s')
            sns.despine(ax=self.axes, left=True, trim=True)
            self.axes.get_yaxis().set_visible(False)

        plt.show()
        self.draw()
        self.resize_event()

        self.draw()