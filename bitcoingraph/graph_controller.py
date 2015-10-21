
from bitcoingraph.blockchain import to_json, to_time
from bitcoingraph.graphdb import GraphDB


class GraphController:

    rows_per_page_default = 20

    def __init__(self, host, port, user, password):
        self.graph_db = GraphDB(host, port, user, password)

    def get_address_info(self, address, date_from=None, date_to=None, rows_per_page=rows_per_page_default):
        result = self.graph_db.address_stats_query(address).single_row()
        if result['num_transactions'] == 0:
            return {'transactions': 0}
        if date_from is None and date_to is None:
            count = result['num_transactions']
        else:
            count = self.graph_db.address_count_query(address, date_from, date_to).single_result()
        entity = self.graph_db.entity_query(address).single_result()
        return {'transactions': result['num_transactions'],
                'first': to_time(result['first'], True),
                'last': to_time(result['last'], True),
                'entity': entity,
                'pages': (count + rows_per_page - 1) // rows_per_page}

    def get_address(self, address, page, date_from=None, date_to=None, rows_per_page=rows_per_page_default):
        if rows_per_page is None:
            query = self.graph_db.address_query(address, date_from, date_to)
        else:
            query = self.graph_db.paginated_address_query(address, date_from, date_to,
                                                          page * rows_per_page, rows_per_page)
        return Address(address, query.get())

    def get_identities(self, address):
        identities = self.graph_db.identity_query(address).single_result()
        return identities

    def get_entity(self, id, max_addresses=rows_per_page_default):
        count = self.graph_db.entity_count_query(id).single_result()
        result = self.graph_db.entity_address_query(id, max_addresses)
        entity = {'id': id, 'addresses': result.get(), 'number_of_addresses': count}
        return entity

    def search_address_by_identity_name(self, name):
        address = self.graph_db.reverse_identity_query(name).single_result()
        return address

    def add_identity(self, address, name, link, source):
        self.graph_db.identity_add_query(address, name, link, source)

    def delete_identity(self, id):
        self.graph_db.identity_delete_query(id)

    def get_path(self, address1, address2):
        return Path(self.graph_db.path_query(address1, address2).get())


class Address:

    def __init__(self, address, outputs):
        self.address = address
        self.outputs = [
            {'txid': o['txid'], 'type': o['type'], 'value': o['value'], 'timestamp': to_time(o['timestamp'])}
            for o in outputs]

    def get_incoming_transactions(self):
        for output in self.outputs:
            if output['type'] == 'OUTPUT':
                yield output

    def get_outgoing_transactions(self):
        for output in self.outputs:
            if output['type'] == 'INPUT':
                yield output

    def get_graph_json(self):
        def value_sum(transactions):
            return sum([trans['value'] for trans in transactions])
        nodes = [{'label': 'Address', 'address': self.address}]
        links = []
        incoming_transactions = list(self.get_incoming_transactions())
        outgoing_transactions = list(self.get_outgoing_transactions())
        if len(incoming_transactions) <= 10:
            for transaction in incoming_transactions:
                nodes.append({'label': 'Transaction', 'txid': transaction['txid'], 'type': 'source'})
                links.append({'source': len(nodes) - 1, 'target': 0,
                              'type': transaction['type'], 'value': transaction['value']})
        else:
            nodes.append({'label': 'Transaction', 'amount': len(incoming_transactions), 'type': 'source'})
            links.append({'source': len(nodes) - 1, 'target': 0,
                          'type': 'OUTPUT', 'value': value_sum(incoming_transactions)})
        if len(outgoing_transactions) <= 10:
            for transaction in outgoing_transactions:
                nodes.append({'label': 'Transaction', 'txid': transaction['txid'], 'type': 'target'})
                links.append({'source': 0, 'target': len(nodes) - 1,
                              'type': transaction['type'], 'value': transaction['value']})
        else:
            nodes.append({'label': 'Transaction', 'amount': len(outgoing_transactions), 'type': 'target'})
            links.append({'source': 0, 'target': len(nodes) - 1,
                          'type': 'INPUT', 'value': value_sum(outgoing_transactions)})
        return to_json({'nodes': nodes, 'links': links})


class Path:

    def __init__(self, raw_path):
        self.raw_path = raw_path

    @property
    def path(self):
        if self.raw_path:
            path = []
            for idx, row in enumerate(self.raw_path):
                if 'txid' in row['node']:
                    transaction = row['node']
                    path.append(transaction)
                else:
                    output = row['node']
                    if idx != 0:
                        path.append(output)
                    path.append(row['address'])
                    if idx != len(self.raw_path) - 1:
                        path.append(output)
            return path
        else:
            return None

    def get_graph_json(self):
        nodes = []
        links = []
        if not self.path:
            return to_json({})
        for pc in self.path:
            if 'address' in pc:
                nodes.append({'label': 'Address', 'address': pc['address']})
            elif 'txid' in pc:
                nodes.append({'label': 'Transaction', 'txid': pc['txid']})
            else:
                links.append({'source': len(nodes) - 1, 'target': len(nodes), 'value': pc['value']})
        return to_json({'nodes': nodes, 'links': links})
