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

# Do not mess with these
TRADE_TYPE = None
MARKET_BUY = "Market Buy"
MARKET_SELL = "Market Sell"
BTC = "BTC"
LAST_TRADE_INFO = ""
LAST_TRADE_PRICE_ASK = 0
LAST_TRADE_PRICE_SELL = 0
INITIAL_STOP_PRICE = 1
STOP_PRICE_DELTA = 20
STOP_PRICE = INITIAL_STOP_PRICE
MINIMUM_BTC_WALLET_PRICE = 0.0001
MKAUTOLOSSBOT_VERSION = "0.0.1"

class Strategy(strategy.Strategy):
    """stop loss/start gain bot"""
    def __init__(self, gox, statuswin):
        strategy.Strategy.__init__(self, gox)
        gox.history.signal_changed.connect(self.slot_changed)
        self.statuswin = statuswin
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
        
        if self.already_executed:
            Strategy.end_bot(self)
            return
        
        if not self.init:
          try:
            #reload wallet
            self.fecthWallet()
          except:
            self.log("Could not retrieve wallet data, retrying...")
            return
          else:
            self.log("Wallet data retrieved...")
            self.init = True 
            #reload prices
            self.fetchPrices()
        else:
          #reload wallet -- need to reload before stop loss logic to know funds !
          self.fecthWallet()
          
          # log previous trade
          if self.btc_wallet > MINIMUM_BTC_WALLET_PRICE:
            self.log("STOP LOSS %.1f" % (STOP_PRICE))
          # check stop loss increase
          if (LAST_TRADE_PRICE_BUY > STOP_PRICE+(STOP_PRICE_DELTA*2) and (self.btc_wallet > MINIMUM_BTC_WALLET_PRICE)):
            STOP_PRICE+=STOP_PRICE_DELTA
            self.log("Increasing STOP LOSS to %.1f" % (STOP_PRICE))
          #log next stop loss  
          if self.btc_wallet > MINIMUM_BTC_WALLET_PRICE:
            self.log("Need to be %.1f USD to NEXT STOP LOSS" % (STOP_PRICE+(STOP_PRICE_DELTA*2)))
            
          # check stop loss decrease&sell
          if (LAST_TRADE_PRICE_SELL < STOP_PRICE) and (self.btc_wallet > MINIMUM_BTC_WALLET_PRICE):
            self.log("STOP LOSS activated !")
            TRADE_TYPE = MARKET_SELL 
            #self.execute_trade()
            self.log_trade()
            #stop stop loss bot
            self.already_executed = True
          else:
            self.log_trade()
            #update status bar
            self.statuswin.addStrategyInformation(" | STOP LOSS: VALUE %.1f DELTA %.1f STATE: %s" % (STOP_PRICE,STOP_PRICE_DELTA,("ACTIVE" if (self.btc_wallet > MINIMUM_BTC_WALLET_PRICE) else "INACTIVE")))

    def slot_keypress(self, gox, key):
        global TRADE_TYPE
        global STOP_PRICE
        global STOP_PRICE_DELTA
        if not self.init:
            self.debug("Bot not initialized!")
            return
        key = chr(key)
        self.log("GOT KEY %s" % (key))
        if key == "k":
             TRADE_TYPE = MARKET_BUY
             self.execute_trade()
             self.log_trade()
        elif key == "m":
             TRADE_TYPE = MARKET_SELL
             self.execute_trade()
             self.log_trade()
             #stop stop loss bot
             self.already_executed = True
        elif key == "s":
           dialog = StopLossDialog(STDSCR, self.gox, curses.color_pair(20), "AUTO STOP LOSS")
           dialog.modal()
           prc, delta = dialog.do_submit(dialog.price, dialog.delta)
           if prc:
                 STOP_PRICE = prc
           if delta:
                 STOP_PRICE_DELTA = delta                
           #update info
           self.log("STOP LOSS Changed by user to %s %s with delta %s" % (STOP_PRICE,self.user_currency,STOP_PRICE_DELTA))
           self.statuswin.addStrategyInformation(" | STOP LOSS: VALUE %.1f DELTA %.1f STATE: %s" % (STOP_PRICE,STOP_PRICE_DELTA,("ACTIVE" if (self.btc_wallet > MINIMUM_BTC_WALLET_PRICE) else "INACTIVE")))

    def end_bot(self):
          STOP_PRICE = 1
          STOP_PRICE_DELTA = 0
          #update status bar
          self.statuswin.addStrategyInformation(" | STOP LOSS: VALUE %.1f DELTA %.1f STATE: %s" % (STOP_PRICE,STOP_PRICE_DELTA,"TRIGGERED"))
          self.log("STOP LOSS BOT DEACTIVATED!!!!!!")
          self.log_trade()
          return
      
    def execute_trade(self):
      global LAST_TRADE_PRICE_SELL
      global LAST_TRADE_PRICE_BUY
      global TRADE_TYPE
      global LAST_TRADE_INFO
      #reload prices
      self.fetchPrices()
      ###
      if not self.init:
          self.debug("Bot not initialized!")
          return
          
      if TRADE_TYPE == MARKET_BUY:
        #
        LAST_TRADE_INFO = " MARKET BUY: VOL %.4f %s -> %f BTC -- at %.4f %s" % (self.fiat_wallet, self.user_currency, (self.fiat_wallet / LAST_TRADE_PRICE_BUY),LAST_TRADE_PRICE_BUY,self.user_currency)
        #
        self.gox.buy(0, int((self.fiat_wallet / LAST_TRADE_PRICE_BUY) * 1e8))
        TRADE_TYPE = None
      elif TRADE_TYPE == MARKET_SELL:
        #
        LAST_TRADE_INFO = " MARKET SELL: VOL %s BTC -> %.4f %s -- at %.4f %s" % (self.btc_wallet, (self.btc_wallet * LAST_TRADE_PRICE_SELL),self.user_currency,LAST_TRADE_PRICE_SELL,self.user_currency)
        #
        self.gox.sell(0, int(self.btc_wallet * 1e8))
        TRADE_TYPE = None 
        
    def log_trade(self):
      global LAST_TRADE_INFO
      if LAST_TRADE_INFO != "":
        self.log(LAST_TRADE_INFO)
        
    def log(self, msg):
      self.debug("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")
      self.debug("                                                                                 ")
      self.debug(15 * " " + msg)
      self.debug("                                                                                 ")
      self.debug("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@")

    def fetchPrices(self):
      global LAST_TRADE_PRICE_BUY
      global LAST_TRADE_PRICE_SELL
      #reload prices
      LAST_TRADE_PRICE_SELL = float(self.gox.orderbook.bid/float(100000))
      LAST_TRADE_PRICE_BUY = float(self.gox.orderbook.ask/float(100000))
      # log
      self.log("Got last price SELL: %.4f %s BUY: %.4f %s" % (LAST_TRADE_PRICE_SELL,self.user_currency,LAST_TRADE_PRICE_BUY,self.user_currency))
      
    def fecthWallet(self):
      self.log("Wallet data refreshed. %s BTC %s %s" % (self.btc_wallet,self.fiat_wallet,self.user_currency))
      self.btc_wallet = goxapi.int2float(self.gox.wallet[BTC], BTC)
      self.fiat_wallet = goxapi.int2float(self.gox.wallet[self.user_currency], self.user_currency)   
        
class StopLossDialog(goxtool.DlgStopLoss):
    def __init__(self, stdscr, gox, color, msg):
        goxtool.DlgStopLoss.__init__(self, stdscr, gox, color, msg)
        self.price = 0
        self.delta = 0
     
    def do_submit(self, price_float, delta_float):
        self.price =  price_float
        self.delta = delta_float
        return price_float, delta_float
