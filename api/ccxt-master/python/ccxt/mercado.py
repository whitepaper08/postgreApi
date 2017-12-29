# -*- coding: utf-8 -*-

from ccxt.base.exchange import Exchange
import hashlib
from ccxt.base.errors import ExchangeError


class mercado (Exchange):

    def describe(self):
        return self.deep_extend(super(mercado, self).describe(), {
            'id': 'mercado',
            'name': 'Mercado Bitcoin',
            'countries': 'BR',  # Brazil
            'rateLimit': 1000,
            'version': 'v3',
            'hasCORS': True,
            'hasWithdraw': True,
            'urls': {
                'logo': 'https://user-images.githubusercontent.com/1294454/27837060-e7c58714-60ea-11e7-9192-f05e86adb83f.jpg',
                'api': {
                    'public': 'https://www.mercadobitcoin.net/api',
                    'private': 'https://www.mercadobitcoin.net/tapi',
                },
                'www': 'https://www.mercadobitcoin.com.br',
                'doc': [
                    'https://www.mercadobitcoin.com.br/api-doc',
                    'https://www.mercadobitcoin.com.br/trade-api',
                ],
            },
            'api': {
                'public': {
                    'get': [
                        '{coin}/orderbook/',  # last slash critical
                        '{coin}/ticker/',
                        '{coin}/trades/',
                        '{coin}/trades/{from}/',
                        '{coin}/trades/{from}/{to}',
                        '{coin}/day-summary/{year}/{month}/{day}/',
                    ],
                },
                'private': {
                    'post': [
                        'cancel_order',
                        'get_account_info',
                        'get_order',
                        'get_withdrawal',
                        'list_system_messages',
                        'list_orders',
                        'list_orderbook',
                        'place_buy_order',
                        'place_sell_order',
                        'withdraw_coin',
                    ],
                },
            },
            'markets': {
                'BTC/BRL': {'id': 'BRLBTC', 'symbol': 'BTC/BRL', 'base': 'BTC', 'quote': 'BRL', 'suffix': 'Bitcoin'},
                'LTC/BRL': {'id': 'BRLLTC', 'symbol': 'LTC/BRL', 'base': 'LTC', 'quote': 'BRL', 'suffix': 'Litecoin'},
                'BCH/BRL': {'id': 'BRLBCH', 'symbol': 'BCH/BRL', 'base': 'BCH', 'quote': 'BRL', 'suffix': 'BCash'},
            },
            'fees': {
                'trading': {
                    'maker': 0.3 / 100,
                    'taker': 0.7 / 100,
                },
            },
        })

    def fetch_order_book(self, symbol, params={}):
        market = self.market(symbol)
        orderbook = self.publicGetCoinOrderbook(self.extend({
            'coin': market['base'],
        }, params))
        return self.parse_order_book(orderbook)

    def fetch_ticker(self, symbol, params={}):
        market = self.market(symbol)
        response = self.publicGetCoinTicker(self.extend({
            'coin': market['base'],
        }, params))
        ticker = response['ticker']
        timestamp = int(ticker['date']) * 1000
        return {
            'symbol': symbol,
            'timestamp': timestamp,
            'datetime': self.iso8601(timestamp),
            'high': float(ticker['high']),
            'low': float(ticker['low']),
            'bid': float(ticker['buy']),
            'ask': float(ticker['sell']),
            'vwap': None,
            'open': None,
            'close': None,
            'first': None,
            'last': float(ticker['last']),
            'change': None,
            'percentage': None,
            'average': None,
            'baseVolume': float(ticker['vol']),
            'quoteVolume': None,
            'info': ticker,
        }

    def parse_trade(self, trade, market):
        timestamp = trade['date'] * 1000
        return {
            'info': trade,
            'timestamp': timestamp,
            'datetime': self.iso8601(timestamp),
            'symbol': market['symbol'],
            'id': str(trade['tid']),
            'order': None,
            'type': None,
            'side': trade['type'],
            'price': trade['price'],
            'amount': trade['amount'],
        }

    def fetch_trades(self, symbol, since=None, limit=None, params={}):
        market = self.market(symbol)
        response = self.publicGetCoinTrades(self.extend({
            'coin': market['base'],
        }, params))
        return self.parse_trades(response, market, since, limit)

    def fetch_balance(self, params={}):
        response = self.privatePostGetAccountInfo()
        balances = response['response_data']['balance']
        result = {'info': response}
        currencies = list(self.currencies.keys())
        for i in range(0, len(currencies)):
            currency = currencies[i]
            lowercase = currency.lower()
            account = self.account()
            if lowercase in balances:
                account['free'] = float(balances[lowercase]['available'])
                account['total'] = float(balances[lowercase]['total'])
                account['used'] = account['total'] - account['free']
            result[currency] = account
        return self.parse_balance(result)

    def create_order(self, symbol, type, side, amount, price=None, params={}):
        if type == 'market':
            raise ExchangeError(self.id + ' allows limit orders only')
        method = 'privatePostPlace' + self.capitalize(side) + 'Order'
        order = {
            'coin_pair': self.market_id(symbol),
            'quantity': amount,
            'limit_price': price,
        }
        response = getattr(self, method)(self.extend(order, params))
        return {
            'info': response,
            'id': str(response['response_data']['order']['order_id']),
        }

    def cancel_order(self, id, symbol=None, params={}):
        if not symbol:
            raise ExchangeError(self.id + ' cancelOrder() requires a symbol argument')
        self.load_markets()
        market = self.market(symbol)
        return self.privatePostCancelOrder(self.extend({
            'coin_pair': market['id'],
            'order_id': id,
        }, params))

    def parse_order(self, order, market=None):
        side = None
        if 'order_type' in order:
            side = 'buy' if (order['order_type'] == 1) else 'sell'
        status = order['status']
        symbol = None
        if not market:
            if 'coin_pair' in order:
                if order['coin_pair'] in self.markets_by_id:
                    market = self.markets_by_id[order['coin_pair']]
        if market:
            symbol = market['symbol']
        timestamp = None
        if 'created_timestamp' in order:
            timestamp = int(order['created_timestamp']) * 1000
        if 'updated_timestamp' in order:
            timestamp = int(order['updated_timestamp']) * 1000
        fee = {
            'cost': float(order['fee']),
            'currency': market['quote'],
        }
        price = self.safe_float(order, 'limit_price')
        # price = self.safe_float(order, 'executed_price_avg', price)
        average = self.safe_float(order, 'executed_price_avg')
        amount = self.safe_float(order, 'quantity')
        filled = self.safe_float(order, 'executed_quantity')
        remaining = amount - filled
        cost = amount * average
        result = {
            'info': order,
            'id': str(order['order_id']),
            'timestamp': timestamp,
            'datetime': self.iso8601(timestamp),
            'symbol': symbol,
            'type': 'limit',
            'side': side,
            'price': price,
            'cost': cost,
            'average': average,
            'amount': amount,
            'filled': filled,
            'remaining': remaining,
            'status': status,
            'fee': fee,
        }
        return result

    def fetch_order(self, id, symbol=None, params={}):
        if not symbol:
            raise ExchangeError(self.id + ' cancelOrder() requires a symbol argument')
        self.load_markets()
        market = self.market(symbol)
        response = None
        response = self.privatePostGetOrder(self.extend({
            'coin_pair': market['id'],
            'order_id': int(id),
        }, params))
        return self.parse_order(response['response_data']['order'])

    def withdraw(self, currency, amount, address, params={}):
        self.load_markets()
        request = {
            'coin': currency,
            'quantity': '{:.10f}'.format(amount),
            'address': address,
        }
        if currency == 'BRL':
            account_ref = ('account_ref' in list(params.keys()))
            if not account_ref:
                raise ExchangeError(self.id + ' requires account_ref parameter to withdraw ' + currency)
        elif currency != 'LTC':
            tx_fee = ('tx_fee' in list(params.keys()))
            if not tx_fee:
                raise ExchangeError(self.id + ' requires tx_fee parameter to withdraw ' + currency)
        response = self.privatePostWithdrawCoin(self.extend(request, params))
        return {
            'info': response,
            'id': response['response_data']['withdrawal']['id'],
        }

    def sign(self, path, api='public', method='GET', params={}, headers=None, body=None):
        url = self.urls['api'][api] + '/'
        if api == 'public':
            url += self.implode_params(path, params)
        else:
            self.check_required_credentials()
            url += self.version + '/'
            nonce = self.nonce()
            body = self.urlencode(self.extend({
                'tapi_method': path,
                'tapi_nonce': nonce,
            }, params))
            auth = '/tapi/' + self.version + '/' + '?' + body
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'TAPI-ID': self.apiKey,
                'TAPI-MAC': self.hmac(self.encode(auth), self.encode(self.secret), hashlib.sha512),
            }
        return {'url': url, 'method': method, 'body': body, 'headers': headers}

    def request(self, path, api='public', method='GET', params={}, headers=None, body=None):
        response = self.fetch2(path, api, method, params, headers, body)
        if 'error_message' in response:
            raise ExchangeError(self.id + ' ' + self.json(response))
        return response
