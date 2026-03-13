import mysql.connector

class WDb():
    def __init__(self):
        self.connecty = None
        self.openCon()
    
    def openCon(self):
        if self.connecty: self.connecty.close()
        self.connecty = mysql.connector.connect(
            host='3.26.64.170', database='waimanakopok', user='waimanako', password="Space2B!", port=3307)
        self.cursor = self.connecty.cursor(dictionary=True)
        # self.log("Wspace Mysql connection opened.")

    def store(self, query):
        self.cursor.execute(query)
        self.connecty.commit()

    def fetch(self, query):
        self.cursor.execute(query)
        return self.cursor.fetchall()


