import json

class Gig():
    # A gig is the object that relates to a koha transaction
    def __init__(self, gigData):
        self.gigId = gigData['gigId']
        self.gigIsComplete = gigData['gigIsComplete']
        self.tableName = gigData['tableName']
        self.createdDate = gigData['createdDate']
        if 'screenMe' not in gigData: 
                gigData['screenMe'] = 1
                self.screenMe = 1
        else: self.screenMe = gigData['screenMe']
        self.gigData = gigData
        
        self.gigMessage = GigMessages(gigData['messages'])
        self.gigItems = []
        self.baristaItems = []
        self.chillItems = []
        self.kitchenItems = []
        self.awaitingUpdate = False

        served = self.gigIsComplete or "Served" in self.gigMessage.record
        self.baristaDelivered = True
        self.chillsDelivered = True
        self.kitchenDelivered = True

        for i in gigData['picked']:
            for key, value in i.items():
                item = GigItem(key, value)
                self.gigItems.append(item)
                
                if "Barista" in key:
                    self.baristaItems.append(item)
                    if (served and self.baristaDelivered and not item.beenDelivered):
                        self.baristaDelivered = False 

                elif "Ices" in key or "Fridge" in key:
                    self.chillItems.append(item)
                    if (served and self.chillsDelivered and not item.beenDelivered):
                        self.chillsDelivered = False

                elif "Kitchen" in key:
                    self.kitchenItems.append(item)
                    if (served and self.kitchenDelivered and not item.beenDelivered):
                        self.kitchenDelivered = False

    def getPlateCount(self, isBarista, isKitchen, pending):
        items = self.getItems(isBarista, isKitchen)
        matchingItems = filter(lambda gig: (pending and not gig.beenDelivered) or (not pending and gig.beenDelivered), items)
        return list(matchingItems).__len__()

    def getItems(self, isBarista, isKitchen):
        if (isKitchen):
            return self.kitchenItems
        elif (isBarista):
            return self.baristaItems
        else:
            return self.chillItems

    def deliverItem(self, isBarista, isKitchen, itemIndex, deliver):
        self.awaitingUpdate = True

        items = self.getItems(isBarista, isKitchen)
        items[itemIndex].setAsDelivered(deliver)

    def exportGig(self):
        self.gigData["picked"] = []
        for i in self.gigItems:
            self.gigData["picked"].append({i.key: i.data})

        self.awaitingUpdate = False
        return json.dumps(self.gigData)

class GigMessages():

    def __init__(self, messages):
        self.record = messages['Record']
        self.chills = messages['Ices']
        self.barista = messages['Barista']
        self.kitchen = messages['Kitchen']

class GigItem():

    def __init__(self, key, data):
        self.key = key
        self.data = data
        self.quantity = data['Quantity:']
        self.tastes = data['Tastes:']

        self.category = key.split("(")[0]
        self.beenDelivered = data['Delivered:'] == "Yes"

    def setAsDelivered(self, deliver):
        self.beenDelivered = deliver

        if (deliver):
            self.data['Delivered:'] = "Yes"
        else:
            self.data['Delivered:'] = "Unknown"
