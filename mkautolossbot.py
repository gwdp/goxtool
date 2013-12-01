"""
The file can be reloaded after editing without restarting goxtool by simply pressing the (l) key.
"""
# Using the global statement
# pylint: disable=W0603
# No exception type(s) specified
# pylint: disable=W0702
# Missing docstring
# pylint: disable=C0111
# Line too long
# pylint: disable=C0301

import curses
import curses.panel
import curses.textpad
import strategy
import goxapi
import goxtool
STDSCR = curses.initscr()


# User defined variables
INITIAL_STOP_PRICE = 1
STOP_PRICE_DELTA = 0
# For Internal Bot usage - don't mess with these
TRADE_TYPE = None
TRADE_TYPE_MARKET_BUY = "Market Buy"
TRADE_TYPE_MARKET_SELL = "Market Sell"
TRADE_TYPE_FIRST_SELL_ORDER = "First Sell Order"
TRADE_TYPE_FIRST_BUY_ORDER = "First Buy Order"
SELL = "Market Sell"
BTC = "BTC"
LAST_TRADE_INFO = ""
LAST_TRADE_PRICE_ASK = 0
LAST_TRADE_PRICE_SELL = 0
TRIGGERED_TRADE_PRICE_SELL = 0
STOP_PRICE = INITIAL_STOP_PRICE
MINIMUM_BTC_WALLET_PRICE = 0.0001
INSERT_ORDER_DIFFERENCE = 0.00001
MKAUTOLOSSBOT_VERSION = "0.0.2"


class Strategy(strategy.Strategy):
    """stop loss/start gain bot"""
    def __init__(self, gox, statuswin):
        strategy.Strategy.__init__(self, gox)
        gox.history.signal_changed.connect(self.slot_changed)
        self.statuswin = statuswin
        self.statuswin.addStrategyInformation("") #reset in initialization
        self.init = False
        self.got_wallet = False
        self.already_executed = False
        self.log("Initialized MKAUTOLOSSBOT IN VERSION %s" % (MKAUTOLOSSBOT_VERSION))

        self.user_currency = gox.currency
        self.total_filled = 0 
        self.btc_wallet = 0
        self.fiat_wallet = 0

    def slot_changed(self, history, _no_data):
        global TRADE_TYPE
        global LAST_TRADE_INFO
        global LAST_TRADE_PRICE_SELL
        global LAST_TRADE_PRICE_BUY
        global STOP_PRICE_DELTA
        global STOP_PRICE
        global TRADE_TYPE_MARKET_SELL
        
        if self.already_executed:
            Strategy.end_bot(self)
            return
        
        if not self.init:
            #reload wallet
            self.fecthWallet()
            #mark as initialized
            self.init = True 
            #reload prices
            self.fetchPrices()
        else:
          #reload wallet -- need to reload before stop loss logic to know funds !
          self.fecthWallet()
          #reload prices -- need to reload before stop loss logic to price !
          self.fetchPrices()
          
          # reset bot in case user add bitcoin in wallet and the bot activate and sell for mistake
          if self.btc_wallet <= MINIMUM_BTC_WALLET_PRICE:
            STOP_PRICE = 1
            STOP_PRICE_DELTA = 0
            
          # check stop loss increase
          if (LAST_TRADE_PRICE_BUY > STOP_PRICE+(STOP_PRICE_DELTA*2) and \
             (self.btc_wallet > MINIMUM_BTC_WALLET_PRICE)) and \
             STOP_PRICE_DELTA:
               STOP_PRICE+=STOP_PRICE_DELTA
               self.log("Increasing STOP LOSS to %.8f" % (STOP_PRICE))
               self.log("Need to be %.8f %s to NEXT STOP LOSS %8.f %s" % (STOP_PRICE+(STOP_PRICE_DELTA*2),self.user_currency,(STOP_PRICE+STOP_PRICE_DELTA),self.user_currency))
          elif (self.btc_wallet > MINIMUM_BTC_WALLET_PRICE):
               self.log("STOP LOSS %.8f" % (STOP_PRICE))
            
          # check stop loss decrease&sell
          if (LAST_TRADE_PRICE_SELL < STOP_PRICE) and (self.btc_wallet > MINIMUM_BTC_WALLET_PRICE):
            self.log("STOP LOSS activated !")
            TRADE_TYPE = TRADE_TYPE_MARKET_SELL 
            #self.execute_trade()
            self.log_trade()
            #stop stop loss bot
            self.already_executed = True
          else:
            self.log_trade()
            #update status bar
            self.writeStatusInStatusBar(False)

    def end_bot(self):
          global TRIGGERED_TRADE_PRICE_SELL
          global STOP_PRICE
          global STOP_PRICE_DELTA
          STOP_PRICE = 1
          STOP_PRICE_DELTA = 0
          #update status bar
          self.writeStatusInStatusBar(True)
          self.log("STOP LOSS BOT DEACTIVATED!!!!!!")
          self.log_trade()
          return
          
    def fecthWallet(self):
      global BTC
      self.btc_wallet = goxapi.int2float(self.gox.wallet[BTC], BTC)
      self.fiat_wallet = goxapi.int2float(self.gox.wallet[self.user_currency], self.user_currency)   
      self.log("Wallet data refreshed. | %.8f BTC | %.8f %s |" % (self.btc_wallet,self.fiat_wallet,self.user_currency))
      
    def fetchPrices(self):
      global LAST_TRADE_PRICE_BUY
      global LAST_TRADE_PRICE_SELL
      #reload prices
      LAST_TRADE_PRICE_SELL = float(self.gox.orderbook.bid/float(100000))
      LAST_TRADE_PRICE_BUY = float(self.gox.orderbook.ask/float(100000))
      # log
      self.log("Got last price SELL: %.8f %s BUY: %.8f %s" % (LAST_TRADE_PRICE_SELL,self.user_currency,LAST_TRADE_PRICE_BUY,self.user_currency))
    #display info methods
    def log_trade(self):
      global LAST_TRADE_INFO
      self.log(LAST_TRADE_INFO)
    def log(self, msg):
      if msg != "":
        self.debug("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
        self.debug("                                                                                 ")
        self.debug(15 * " " + msg)
        self.debug("                                                                                 ")
        self.debug("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
        
    def writeStatusInStatusBar(self,isTriggered):
      global MINIMUM_BTC_WALLET_PRICE
      global STOP_PRICE
      global STOP_PRICE_DELTA
      global TRIGGERED_TRADE_PRICE_SELL
      BOT_STATE = (("TRIGERRED at %.4f" % (TRIGGERED_TRADE_PRICE_SELL)) if isTriggered \
                  else ("ACTIVE" if (self.btc_wallet > MINIMUM_BTC_WALLET_PRICE) \
                  else "INACTIVE"))
      self.statuswin.addStrategyInformation(" | Stop Loss (%s): VALUE %.4f DELTA %.4f" % (BOT_STATE,STOP_PRICE,STOP_PRICE_DELTA))
    ### actions
    def execute_trade(self):
      global LAST_TRADE_PRICE_SELL
      global LAST_TRADE_PRICE_BUY
      global TRIGGERED_TRADE_PRICE_SELL
      global TRADE_TYPE
      global TRADE_TYPE_MARKET_BUY
      global TRADE_TYPE_MARKET_SELL
      global TRADE_TYPE_FIRST_SELL_ORDER
      global TRADE_TYPE_FIRST_BUY_ORDER
      global INSERT_ORDER_DIFFERENCE
      global LAST_TRADE_INFO
      #reload prices
      self.fetchPrices()
      ###
      if not self.init:
          self.debug("Bot not initialized!")
          return
      if TRADE_TYPE == TRADE_TYPE_MARKET_BUY:
        #Write Info
        LAST_TRADE_INFO = " MARKET BUY: VOL %.8f %s -> %.8f BTC -- at %.8f %s" % \
        (self.fiat_wallet, self.user_currency, (self.fiat_wallet / LAST_TRADE_PRICE_BUY),LAST_TRADE_PRICE_BUY,self.user_currency)
        #Order
        self.gox.buy(0, self.gox.base2int((self.fiat_wallet / LAST_TRADE_PRICE_BUY)))
        TRADE_TYPE = None
      elif TRADE_TYPE == TRADE_TYPE_MARKET_SELL:
        #Write Info
        TRIGGERED_TRADE_PRICE_SELL = LAST_TRADE_PRICE_SELL
        LAST_TRADE_INFO = " MARKET SELL: VOL %.8f BTC -> %.8f %s -- at %.8f %s" % \
        (self.btc_wallet, (self.btc_wallet * LAST_TRADE_PRICE_SELL),self.user_currency,LAST_TRADE_PRICE_SELL,self.user_currency)
        #Order
        self.gox.sell(0, self.gox.base2int(self.btc_wallet))
        TRADE_TYPE = None
      elif TRADE_TYPE == TRADE_TYPE_FIRST_SELL_ORDER:
        #Write Info
        tradeValue = LAST_TRADE_PRICE_BUY-INSERT_ORDER_DIFFERENCE
        LAST_TRADE_INFO = " SELL ORDER: VOL %.8f BTC -> %.8f %s -- at %.8f %s" % \
        (self.btc_wallet, (self.btc_wallet * tradeValue),self.user_currency,tradeValue,self.user_currency)
        #Order
        self.gox.sell(self.gox.quote2int(tradeValue), self.gox.base2int(self.btc_wallet))
        TRADE_TYPE = None
      elif TRADE_TYPE == TRADE_TYPE_FIRST_BUY_ORDER:
        #Write Info
        tradeValue = LAST_TRADE_PRICE_SELL+INSERT_ORDER_DIFFERENCE
        LAST_TRADE_INFO = " MARKET BUY: VOL %.8f %s -> %.8f BTC -- at %.8f %s" % \
        (self.fiat_wallet, self.user_currency, (self.fiat_wallet / tradeValue),tradeValue,self.user_currency)
        #Order
        self.gox.buy(self.gox.quote2int(tradeValue), self.gox.base2int((self.fiat_wallet / tradeValue)))
        TRADE_TYPE = None
        
    def slot_keypress(self, gox, key):
        global TRADE_TYPE
        global STOP_PRICE
        global STOP_PRICE_DELTA
        global TRADE_TYPE_MARKET_BUY
        global TRADE_TYPE_MARKET_SELL
        global TRADE_TYPE_FIRST_SELL_ORDER
        global TRADE_TYPE_FIRST_BUY_ORDER
        if not self.init:
            self.debug("Bot not initialized!")
            return
            
        key = chr(key)
        self.log("GOT KEY %s" % (key))
        if key == "k":
             TRADE_TYPE = TRADE_TYPE_MARKET_BUY
             self.execute_trade()
             self.log_trade()
        elif key == "m":
             TRADE_TYPE = TRADE_TYPE_MARKET_SELL
             self.execute_trade()
             self.log_trade()
             #stop stop loss bot
             self.already_executed = True
        elif key == "a":
           TRADE_TYPE = TRADE_TYPE_FIRST_SELL_ORDER
           self.execute_trade()
           self.log_trade()
        elif key == "c":
           TRADE_TYPE = TRADE_TYPE_FIRST_BUY_ORDER
           self.execute_trade()
           self.log_trade()
        elif key == "s":
           dialog = StopLossDialog(STDSCR, self.gox, curses.color_pair(20), "AUTO STOP LOSS")
           dialog.modal()
           prc, delta = dialog.do_submit(dialog.price, dialog.delta)
           if prc:
                 STOP_PRICE = prc
           if delta:
                 STOP_PRICE_DELTA = delta                
           #update info
           self.log("STOP LOSS Changed by user to %.8f %s with delta %.8f" % (STOP_PRICE,self.user_currency,STOP_PRICE_DELTA))
           self.writeStatusInStatusBar(False)
          
class StopLossDialog(goxtool.DlgStopLoss):
    def __init__(self, stdscr, gox, color, msg):
        goxtool.DlgStopLoss.__init__(self, stdscr, gox, color, msg)
        self.price = 0
        self.delta = 0
     
    def do_submit(self, price_float, delta_float):
        self.price =  price_float
        self.delta = delta_float
        return price_float, delta_float
