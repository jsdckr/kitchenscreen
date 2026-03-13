#!/usr/bin/python3
# from PyQt5.QtWidgets import * 
from PyQt5.QtCore import *
from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtWidgets import *
from datetime import datetime, timedelta
from datetime import date
from threading import Thread
import vlc
import time
from pynput.keyboard import Key, Controller
import json
from GatheringWindow import Ui_gatheringWindow
from DatabaseFunctions import WDb
from GigModel import Gig
import sys

class GatheringDisplay(QtWidgets.QDialog,Ui_gatheringWindow):

    def __init__(self, parent=None, isKitchen=False, targetScreen=None):
        super(GatheringDisplay, self).__init__(parent)
        self.setupUi(self)

        # Move to the target screen BEFORE going fullscreen
        if targetScreen is not None:
            screens = QApplication.screens()
            if 0 <= targetScreen < len(screens):
                geom = screens[targetScreen].geometry()
                self.move(geom.topLeft())
                self._targetScreen = screens[targetScreen]
            else:
                print(f"Warning: screen index {targetScreen} not found "
                      f"(have {len(screens)} screens). Using default.")
                self._targetScreen = QApplication.primaryScreen()
        else:
            self._targetScreen = QApplication.primaryScreen()

        self.showFullScreen()
        flags = Qt.WindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setWindowFlags(flags)
        self.pending = True
        self.isKitchen = isKitchen
        self.lastChillsUpdated = None
        self.lastBaristaUpdated = None
        if self.isKitchen: self.kitchenMode()
        self.lastCount = {'Kitchen Gigs - ': 0, 'Barista Gigs - ': 0, 'Chills Gigs - ': 0}
        self.lastCompletedCount = {'Kitchen Gigs - ': 0, 'Barista Gigs - ': 0, 'Chills Gigs - ': 0}
        self._numCols = 2
        self._fontSize = 18
        self.leftOffset = {'Barista Gigs - ': 0, 'Chills Gigs - ': 0}
        self.lastActivity = {'Barista Gigs - ': int(datetime.now().timestamp()), 'Chills Gigs - ': int(datetime.now().timestamp())}
        self.inactivityReset = 120 # number of seconds before resetting the offset
        self.keyboard = Controller()
        QTimer.singleShot(0, self._initAfterShow)

    def _initAfterShow(self):
        self.setHeightsAndWidth()
        self.loadTodayData()

        # Add a quit button to the top bar, before the 'Go Left' button
        self.quitBtn = QtWidgets.QPushButton("✕  Quit")
        self.quitBtn.setStyleSheet(
            "font: 12pt 'ubuntu'; background-color: rgb(200, 50, 50); "
            "color: white; padding: 4px 12px; border-radius: 4px;"
        )
        self.quitBtn.setMaximumSize(QtCore.QSize(120, 30))
        quitIndex = self.horizontalLayout_6.indexOf(self.baristaLeft)
        self.horizontalLayout_6.insertWidget(quitIndex, self.quitBtn)
        self.quitBtn.clicked.connect(self.quitApp)

        self.toggleCompletedGigs.clicked.connect(lambda: self.toggleCompletedPending())
        self.baristaLeft.clicked.connect(lambda: self.leftRightButtons('Barista Gigs - ', True))
        self.baristaRight.clicked.connect(lambda: self.leftRightButtons('Barista Gigs - ', True, False))
        self.chillsLeft.clicked.connect(lambda: self.leftRightButtons('Chills Gigs - ', True))
        self.chillsRight.clicked.connect(lambda: self.leftRightButtons('Chills Gigs - ', True, False))
        self.timer = QTimer()
        self.timer.timeout.connect(self.updateGigs)
        self.timer.start(5000)
        

    def leftRightButtons(self, pickedLayer='Barista Gigs - ', wasClicked=False, clickedLeft=True):
        # This determines whether or not the left and right buttons on each layer is live, and reacts to button clicks
        if pickedLayer == 'Barista Gigs - ': 
            pickedLButton = self.baristaLeft
            pickedRButton = self.baristaRight
        else: 
            pickedLButton = self.chillsLeft 
            pickedRButton = self.chillsRight

        # Now we respond to a button click
        if wasClicked: self.leftRightButtonsClicked(pickedLayer, clickedLeft) 

        if self.pending:
            if self.isKitchen:
                lastCount = self.lastCount["Kitchen Gigs - "]
            else:
                lastCount = self.lastCount[pickedLayer]
        else:
            if self.isKitchen:
                lastCount = self.lastCompletedCount["Kitchen Gigs - "]
            else:
                lastCount = self.lastCompletedCount[pickedLayer]

        if (self.leftOffset[pickedLayer] == 0):
            pickedLButton.setEnabled(False)
        else:
            pickedLButton.setEnabled(True)

        if (self.leftOffset[pickedLayer] >= (lastCount - self._numCols)):
            pickedRButton.setEnabled(False)
        else:
            pickedRButton.setEnabled(True)

    
    def leftRightButtonsClicked(self, pickedLayer, clickedLeft):
        # The user selected the left or right button on the Chills or Barista layer
        self.lastActivity[pickedLayer] = int(datetime.now().timestamp())
        if (clickedLeft):
            self.leftOffset[pickedLayer] -= 1
        else:
            self.leftOffset[pickedLayer] += 1
        self.displayGigs()

        
    def toggleCompletedPending(self):
        self.pending = not self.pending
        if self.pending:
            self.toggleCompletedGigs.setText("Show COMPLETED Gigs")
        else:
            self.toggleCompletedGigs.setText("Show PENDING Gigs")
        self.leftOffset["Barista Gigs - "] = 0
        self.leftOffset["Chills Gigs - "] = 0
        self.lastActivity["Barista Gigs - "] = int(datetime.now().timestamp())
        self.lastActivity["Chills Gigs - "] = int(datetime.now().timestamp())
        self.updateGigs()


    def loadTodayData(self):
        startDate = date.today()
        # Testing: startDate = date.today() - timedelta(days=1)
        tomorrow = startDate + timedelta(days=1)
        dayBegin = int(datetime.combine(startDate, datetime.min.time()).timestamp())
        dayEnd = int(datetime.combine(tomorrow, datetime.min.time()).timestamp())
        query = "SELECT gig_data, gig_iscomplete FROM pok_gigs WHERE gig_id > " + str(dayBegin) + " AND gig_id < " + str(dayEnd) 
        query = query + " ORDER BY gig_id"
        res = WDb().fetch(query)
        self.gigsToDisplay = []

        for q in res:
            j = json.loads(q['gig_data'])
            gig = Gig(j)
            if self.shouldDisplay(True, gig):
                self.gigsToDisplay.append(gig)
            elif self.shouldDisplay(False, gig):
                self.gigsToDisplay.append(gig)
        
        if not self.pending:
            self.gigsToDisplay.reverse()
        self.displayGigs()

    def _gig_widgets(self, prefix, index):
        """Return (table_label, date_label, gig_frame, gig_layout) for a gig card."""
        return (
            getattr(self, prefix + "_table_" + str(index)),
            getattr(self, prefix + "_date_" + str(index)),
            getattr(self, prefix + "_gig_" + str(index)),
            getattr(self, prefix + "_gig_layout_" + str(index)),
        )

    def _updateColumns(self):
        """Adjust visible column count and font size based on gig count."""
        baristaGigs = sum(1 for g in self.gigsToDisplay
                          if self.shouldDisplay(True, g))
        if self.isKitchen:
            maxGigs = baristaGigs
        else:
            chillsGigs = sum(1 for g in self.gigsToDisplay
                             if self.shouldDisplay(False, g))
            maxGigs = max(baristaGigs, chillsGigs)

        numCols = min(6, max(2, maxGigs + 1))
        self._numCols = numCols

        # Larger font when fewer columns are visible
        fontMap = {2: 18, 3: 16, 4: 14, 5: 13, 6: 12}
        self._fontSize = fontMap.get(numCols, 12)

        screenGeometry = self._targetScreen.geometry()
        screenWidth = screenGeometry.width()
        screenHeight = screenGeometry.height()
        otherFrameHeight = self.frame.height() + self.frame_2.height()

        width = screenWidth / (numCols + 0.1)
        if self.isKitchen:
            height = screenHeight - 100
        else:
            height = (screenHeight - otherFrameHeight - 50) / 2

        for i in range(1, 7):
            frame = getattr(self, "barista_" + str(i))
            if i <= numCols:
                frame.show()
                if self.isKitchen:
                    frame.setFixedHeight(int((height) - 20))

#                    frame.setFixedHeight(int((height) + self.frame_2.height() - 20))

                else:
                    frame.setFixedHeight(int(height))
                frame.setFixedWidth(int(width))
            else:
                frame.hide()

        for i in range(1, 7):
            frame = getattr(self, "chills_" + str(i))
            if i <= numCols and not self.isKitchen:
                frame.show()
                frame.setFixedHeight(int(height))
                frame.setFixedWidth(int(width))
            else:
                frame.hide()

    def displayGigs(self):
        self._updateColumns()
        baristaIndex = 1
        chillsIndex = 1
        baristaOffset = self.leftOffset["Barista Gigs - "]
        chillsOffset = self.leftOffset["Chills Gigs - "]

        tablePrefix = "Table: "
        if not self.pending:
            tablePrefix = "Completed: "

        for index, gig in enumerate(self.gigsToDisplay):
            if self.isKitchen:
                if self.shouldDisplay(True, gig) and baristaIndex <= (baristaOffset + self._numCols):
                    if baristaIndex > baristaOffset:
                        slot = baristaIndex - baristaOffset
                        table_lbl, date_lbl, gig_frame, gig_layout = self._gig_widgets("barista", slot)
                        table_lbl.setText(tablePrefix + gig.tableName.replace('"', '').replace("'", ""))
                        self.lastBaristaUpdated = "self.barista_table_" + str(slot)
                        date_lbl.setText(gig.createdDate)
                        self.displayGigItems(gig.kitchenItems, gig_frame, gig_layout, index, True, self.grabServer(gig, gig.gigMessage.kitchen))
                    baristaIndex += 1
            else:
                if self.shouldDisplay(True, gig) and baristaIndex <= (baristaOffset + self._numCols):
                    if baristaIndex > baristaOffset:
                        slot = baristaIndex - baristaOffset
                        table_lbl, date_lbl, gig_frame, gig_layout = self._gig_widgets("barista", slot)
                        table_lbl.setText(tablePrefix + gig.tableName.replace('"', '').replace("'", ""))
                        self.lastBaristaUpdated = "self.barista_table_" + str(slot)
                        date_lbl.setText(gig.createdDate)
                        self.displayGigItems(gig.baristaItems, gig_frame, gig_layout, index, True, self.grabServer(gig, gig.gigMessage.barista))
                    baristaIndex += 1
                if self.shouldDisplay(False, gig) and chillsIndex <= (chillsOffset + self._numCols):
                    if chillsIndex > chillsOffset:
                        slot = chillsIndex - chillsOffset
                        table_lbl, date_lbl, gig_frame, gig_layout = self._gig_widgets("chills", slot)
                        table_lbl.setText(tablePrefix + gig.tableName.replace('"', '').replace("'", ""))
                        self.lastChillsUpdated = "self.chills_table_" + str(slot)
                        date_lbl.setText(gig.createdDate)
                        self.displayGigItems(gig.chillItems, gig_frame, gig_layout, index, False, self.grabServer(gig, gig.gigMessage.chills))
                    chillsIndex += 1

        self.emptyGigs("barista", baristaIndex)
        self.emptyGigs("chills", chillsIndex)
        self.updateGigLabels()

    def grabServer(self, gig, message):
        # Show who served the Gig
        if " Served the Gig" in gig.gigMessage.record:
            if "Parked" in gig.gigMessage.record:
                server = gig.gigMessage.record.split(" Parked and Served the Gig")[0]
            else:
                server = gig.gigMessage.record.split(" Served the Gig")[0]
        else: server = "Unknown"
        if message:
            if server in message: return message
        return "Till: " + server + "\n" + message


    def shouldDisplay(self, isBarista, gig):
        if not gig.screenMe: return False
        if self.isKitchen:
            if self.pending and not gig.kitchenDelivered:
                return True
            if not self.pending and gig.kitchenDelivered and len(gig.kitchenItems) > 0:
                return True
        elif isBarista:
            if self.pending and not gig.baristaDelivered:
                return True
            if not self.pending and gig.baristaDelivered and len(gig.baristaItems) > 0:
                return True
        else:
            if self.pending and not gig.chillsDelivered:
                return True
            if not self.pending and gig.chillsDelivered and len(gig.chillItems) > 0:
                return True

        return False

    def emptyGigs(self, typey, startIndex):
        for i in range(startIndex, self._numCols + 1):
            getattr(self, typey + "_table_" + str(i)).setText("")
            getattr(self, typey + "_date_" + str(i)).setText("")
            self.clearChildrenFromLayout(getattr(self, typey + "_gig_layout_" + str(i)))

    def clearChildrenFromLayout(self, layout):
        for i in reversed(range(layout.count())): 
            layout.itemAt(i).widget().setParent(None)

    def displayGigItems(self, gigItems, frame, layout, gigIndex, isBarista, message):
        self.clearChildrenFromLayout(layout)
        layout.setContentsMargins(4, 4, 16, 4)

        if message and "Zero Koha Transaction" not in message:
            label = QtWidgets.QLabel("<b style='color:red;'>" + message + "</b>")
            label.setWordWrap(True)
            label.setStyleSheet(f"font: {self._fontSize + 2}pt 'ubuntu';")
            layout.addWidget(label)

        completed = []
        pendingCount = sum(1 for item in gigItems if not item.beenDelivered)

        for index, item in enumerate(gigItems):
            if item.beenDelivered:
                completed.append(item.category + "(" + ", ".join(item.tastes) + ")")
            else:
                self.addCheckboxes(index, item, frame, gigIndex, isBarista, layout)

        # Add a 'Serve All' button for pending items
        if pendingCount > 0:
            btnText = "\u2714  Serve" if pendingCount == 1 else "\u2714  Serve All (" + str(pendingCount) + ")"
            serveAllBtn = QtWidgets.QPushButton(btnText)
            serveAllBtn.setStyleSheet(
                f"font: {self._fontSize + 1}pt 'ubuntu'; background-color: rgb(80, 180, 80); "
                "color: white; padding: 8px; border-radius: 4px; margin-top: 6px;"
            )
            serveAllBtn.clicked.connect(
                lambda checked, gi=gigIndex, ib=isBarista, items=gigItems:
                    self.serveAllItems(ib, gi, items)
            )
            layout.addWidget(serveAllBtn)

        if len(completed) > 0:
            completedLabel = QtWidgets.QLabel("<i>Completed:</i> <br/>- " + ", <br/>- ".join(completed))
            completedLabel.setWordWrap(True)
            layout.addWidget(completedLabel)

    def addCheckboxes(self, index, item, frame, gigIndex, isBarista, layout):
        itemText = item.category
        if item.quantity > 1:
            itemText = "*Quantity: " + str(item.quantity) + "*\n" + itemText
        for taste in item.tastes:
            itemText += "\n- " + self.wordwrapme(taste)
        checkbox = QtWidgets.QCheckBox(itemText, frame)
        checkbox.setStyleSheet(f"font: {self._fontSize}pt 'ubuntu';")
        layout.addWidget(checkbox)
        checkbox.stateChanged.connect(lambda: self.deliverItem(isBarista, gigIndex, index, checkbox))


    def wordwrapme(self, string, every=25):
        # Imitate wordwrap
        return '\n'.join(string[i:i+every] for i in range(0, len(string), every))


    def deliverItem(self, isBarista, gigIndex, itemIndex, checkbox):
        if isBarista or self.isKitchen:
            self.lastActivity["Barista Gigs - "] = int(datetime.now().timestamp())
        elif not isBarista and not self.isKitchen:
            self.lastActivity["Chills Gigs - "] = int(datetime.now().timestamp())

        self.gigsToDisplay[gigIndex].deliverItem(isBarista, self.isKitchen, itemIndex, checkbox.isChecked())

    def serveAllItems(self, isBarista, gigIndex, gigItems):
        if isBarista or self.isKitchen:
            self.lastActivity["Barista Gigs - "] = int(datetime.now().timestamp())
        else:
            self.lastActivity["Chills Gigs - "] = int(datetime.now().timestamp())

        for index, item in enumerate(gigItems):
            if not item.beenDelivered:
                self.gigsToDisplay[gigIndex].deliverItem(isBarista, self.isKitchen, index, True)

        self.displayGigs()

    def updateGigs(self):
        if self.pending: #remove is pending for testing
            self.checkForInactivity("Barista Gigs - ")
            if not self.isKitchen:
                self.checkForInactivity("Chills Gigs - ")

        for gig in self.gigsToDisplay:
            if gig.awaitingUpdate:
                data = gig.exportGig()
                data = data.replace("'", "''")
                query = "INSERT INTO pok_gigs (gig_id, gig_data) VALUES('" + str(gig.gigId) + "', '" + str(data) + "') ON DUPLICATE KEY UPDATE gig_data='" + str(data) + "'"
                WDb().store(query)       

        self.loadTodayData()

    def checkForInactivity(self, prefix):
        if self.leftOffset[prefix] > 0:
            if (self.lastActivity[prefix] + self.inactivityReset) < int(datetime.now().timestamp()):
                self.leftOffset[prefix] = 0

    def updateGigLabels(self):
        if self.isKitchen:
            kitchenGigs = [gig for gig in self.gigsToDisplay if self.shouldDisplay(True, gig)]
            self.updateLabels("barista", False, "Kitchen Gigs - ", len(kitchenGigs), self.leftOffset["Barista Gigs - "])
            self.leftRightButtons()
        else:
            baristaGigs = [gig for gig in self.gigsToDisplay if self.shouldDisplay(True, gig)]
            self.updateLabels("barista", True, "Barista Gigs - ", len(baristaGigs), self.leftOffset["Barista Gigs - "])
            self.leftRightButtons()

            chillGigs = [gig for gig in self.gigsToDisplay if self.shouldDisplay(False, gig)]
            self.updateLabels("chills", False, "Chills Gigs - ", len(chillGigs), self.leftOffset["Chills Gigs - "])
            self.leftRightButtons('Chills Gigs - ')

    def sOrNot(self, count):
        if (count == 1):
            return ""
        return "s"

    def play_sound(self, path):
        p = vlc.MediaPlayer(path)
        p.play()
        # Give VLC a moment to start; then you can return if you don't care when it finishes
        time.sleep(0.1)

    def updateLabels(self, typey, isBarista, prefix, gigsLength, leftOffset):
        label = getattr(self, typey + "_gigs_label")
        plateCount = sum(i.getPlateCount(isBarista, self.isKitchen, self.pending) for i in self.gigsToDisplay)

        text = str(gigsLength) + " Queued (" + str(plateCount) + " Plate" + self.sOrNot(plateCount) +")" 
        if not self.pending:
            text = str(gigsLength) + " Completed (" + str(plateCount) + " Plate" + self.sOrNot(plateCount) +")" 

        if gigsLength == 0:
            text = "All Done,  Ka Pai!"
            if not self.pending:
                text = "None Completed Today"

        if leftOffset > 0 and self.pending: #remove is pending for testing
            text += " <b style='color:red;'>(" + str(leftOffset) + " OLDER GIG(S) TO THE LEFT)</b>"

        label.setText(prefix + text)
        # Alert with a fun sound 
        if self.pending: 
            if gigsLength == 0: self.lastCount[prefix] = 0
            if (self.lastCount[prefix] < gigsLength) and gigsLength != 0:                 
                if self.isKitchen:
                  quack = Thread(target=self.play_sound, args=("/home/projects/kitchenscreen/chicken.mp3",))
                  quack.start()
                # Blink the Table Name of the last updated:
                if self.lastBaristaUpdated: 
                    if self.isKitchen or 'Barista' in prefix:
                        blinkBarista = Thread(target = self.blinkTableName, args = (self.lastBaristaUpdated, gigsLength, ))
                        blinkBarista.start()
                        self.lastBaristaUpdated = None
                if self.lastChillsUpdated: 
                    if self.isKitchen or 'Chills' in prefix:
                        blinkChills = Thread(target = self.blinkTableName, args = (self.lastChillsUpdated, gigsLength, ))
                        blinkChills.start()
                        self.lastChillsUpdated = None
                    
            self.lastCount[prefix] = gigsLength 
        else:
            self.lastCompletedCount[prefix] = gigsLength
        
        
    def blinkTableName(self, widget, gigsLength):
        if self.isKitchen:
            if 'barista' in widget and gigsLength > self._numCols: return
        else:
            if gigsLength > self._numCols: return
        # Attempt to wake the screen
        self.keyboard.press(Key.shift)
        time.sleep(0.5)
        self.keyboard.release(Key.shift)
        # This created some ishooz, so I'm commenting it out for now...
        # ssBlue = "font: 14pt ; color: rgb(1, 42, 255);"
        # ssRed = "font: 14pt ; color: rgb(255, 0, 0);"
        # for i in range(20):            
        #     eval(widget + ".setStyleSheet(" + '"' + ssRed + '")') 
        #     time.sleep(0.5)
        #     eval(widget + ".setStyleSheet(" + '"' + ssBlue + '")')
        #     time.sleep(0.5)
        

    def setHeightsAndWidth(self):
        # Remove max-height caps set in the .ui file so our calculated sizes take effect
        self.baristaFrame.setMaximumHeight(16777215)
        if not self.isKitchen:
            self.chillerFrame.setMaximumHeight(16777215)

        # Use target screen geometry — self.height()/width() may not
        # reflect fullscreen dimensions yet on X11
        screenGeometry = self._targetScreen.geometry()
        screenWidth = screenGeometry.width()
        screenHeight = screenGeometry.height()
        otherFrameHeight = self.frame.height() + self.frame_2.height()
        width = (screenWidth / 6.1) 
        if self.isKitchen: height = (screenHeight - 50)
        else: height = (screenHeight - otherFrameHeight - 50) / 2

        for i in range(1, 7):
            frame = getattr(self, "barista_" + str(i))
            frame.setMaximumSize(QtCore.QSize(16777215, 16777215))
            if self.isKitchen:
                frame.setFixedHeight(int((height * 2) + self.frame_2.height() - 20))
            else:
                frame.setFixedHeight(int(height))
            frame.setFixedWidth(int(width + 60))

        for i in range(1, 7):
            frame = getattr(self, "chills_" + str(i))
            frame.setMaximumSize(QtCore.QSize(16777215, 16777215))
            if self.isKitchen:
                frame.hide()
            else:
                frame.setFixedHeight(int(height))
            frame.setFixedWidth(int(width + 60))

    def kitchenMode(self):
        self.chills_gigs_label.hide()
        self.chillsLeft.hide()
        self.chillsRight.hide()

    def quitApp(self):
        self.timer.stop()
        QApplication.quit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    isKitchen = False
    targetScreen = None

    # Parse arguments: isKitchen, --screen N
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "isKitchen":
            isKitchen = True
        elif args[i] == "--screen" and i + 1 < len(args):
            targetScreen = int(args[i + 1])
            i += 1
        i += 1

    # List available screens for reference
    for idx, screen in enumerate(app.screens()):
        g = screen.geometry()
        print(f"  Screen {idx}: {screen.name()} — {g.width()}x{g.height()} at +{g.x()}+{g.y()}")

    gd = GatheringDisplay(None, isKitchen, targetScreen)
    gd.exec_()

