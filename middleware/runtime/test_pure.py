"""The parts of the runtime that need neither NVDA nor a browser: the snapshot lookups, the order snapshots are taken in, the WebSocket client against a server of the tests' own."""
import base64, hashlib, os, socket, struct, sys, threading, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import predict, main, wsclient


def node(ix, role, name='', kids=(), **extra): return {'ix': ix, 'uid': 100 + ix, 'role': role, 'name': name, 'childrenIx': list(kids), 'state': {}, **extra}


def snap(nodes, focus=0): return {'nodes': nodes, 'focusIx': focus, 'sel': {}, 'url': 'http://x/', 't': 1, 'page': 1}


class Snapshot(unittest.TestCase):
    def setUp(self):
        self.s = predict.index_children(snap([node(0, 'rootWebArea', kids=[1, 2]), node(1, 'button', 'Save', htmlTag='button', htmlId='save'), node(2, 'button', 'Cancel', htmlTag='button')], focus=2))

    def test_parents_and_children_are_found_by_index(self):
        self.assertEqual([n['ix'] for n in self.s['_index'][0]], [1, 2])
        self.assertEqual(self.s['_parent'][2]['ix'], 0)

    def test_the_focus_event_of_the_page_is_matched_to_the_node_of_its_tag_and_name(self):
        self.assertEqual(predict.match_focus(self.s, {'tag': 'button', 'id': None, 'names': ['Save']})['ix'], 1)

    def test_an_id_narrows_it(self):
        self.assertEqual(predict.match_focus(self.s, {'tag': 'button', 'id': 'save', 'names': ['Save']})['ix'], 1)
        self.assertIsNone(predict.match_focus(self.s, {'tag': 'button', 'id': 'other', 'names': ['Save']}))

    def test_a_node_the_tree_does_not_have_yet_is_none(self):
        self.assertIsNone(predict.match_focus(self.s, {'tag': 'input', 'id': None, 'names': ['Name']}))

    def test_of_several_fits_the_node_the_tree_has_focused_wins(self):
        two = predict.index_children(snap([node(0, 'rootWebArea', kids=[1, 2]), node(1, 'button', 'Go', htmlTag='button'), node(2, 'button', 'Go', htmlTag='button')], focus=2))
        self.assertEqual(predict.match_focus(two, {'tag': 'button', 'id': None, 'names': ['Go']})['ix'], 2)

    def test_a_control_with_no_name_matches_an_event_with_none(self):
        unnamed = predict.index_children(snap([node(0, 'rootWebArea', kids=[1]), node(1, 'button', '', htmlTag='button')], focus=1))
        self.assertEqual(predict.match_focus(unnamed, {'tag': 'button', 'id': None, 'names': []})['ix'], 1)

    def test_the_node_that_takes_the_focus_has_it_and_is_on_the_screen_and_no_other_node_has_it(self):
        s = predict.index_children(snap([node(0, 'rootWebArea', kids=[1, 2]), node(1, 'button', 'Save', state={'focused': True}), node(2, 'button', 'Cancel', state={'offscreen': True})], focus=1))
        moved = predict.focused_on(s, s['nodes'][2])
        self.assertEqual(moved['focusIx'], 2)
        self.assertEqual([bool(n['state'].get('focused')) for n in moved['nodes']], [False, False, True])
        self.assertFalse(moved['nodes'][2]['state']['offscreen'])
        self.assertTrue(s['nodes'][1]['state']['focused'] and s['nodes'][2]['state']['offscreen'])      # the snapshot itself is not changed

    def test_two_states_that_read_the_same_have_one_signature(self):
        a = predict.index_children(snap([node(0, 'rootWebArea', kids=[1]), node(1, 'button', 'Save')]))
        b = predict.index_children(snap([node(0, 'rootWebArea', kids=[1]), node(1, 'button', 'Save', location={'top': 5})], focus=1))
        c = predict.index_children(snap([node(0, 'rootWebArea', kids=[1]), node(1, 'button', 'Saved')]))
        self.assertEqual(predict.tree_signature(a), predict.tree_signature(b))
        self.assertNotEqual(predict.tree_signature(a), predict.tree_signature(c))

    def test_the_shape_of_a_phrase_is_the_fleets(self):
        self.assertEqual(predict.phrase(['Save  ', 'button  ', 3, ' ']), 'Save, button')


class FocusByNode(unittest.TestCase):
    """A11-234: the page's focus is matched to the tree's node by the DOM node the browser names, and by the name the browser computed, before it is guessed from the element's own text."""
    def links(self, **extra):
        return predict.index_children(snap([node(0, 'rootWebArea', kids=[1, 2]),
                                            node(1, 'link', 'Read more (link opens a new window)', htmlTag='a', backendId=40, **extra), node(2, 'link', 'Read more (link opens a new window)', htmlTag='a', backendId=41, **extra)], focus=1))

    def test_the_dom_node_the_browser_names_is_the_node_even_where_the_name_the_page_could_make_is_not_the_trees(self):
        event = {'tag': 'a', 'id': None, 'names': ['Read more'], 'backendNodeId': 41}
        self.assertEqual(predict.match_focus(self.links(), event, last_resort=False)['ix'], 2)

    def test_the_dom_node_wins_over_the_node_the_tree_has_focused_and_over_a_name_that_fits_both(self):
        event = {'tag': 'a', 'id': None, 'names': ['Read more (link opens a new window)'], 'backendNodeId': 41, 'axName': 'Read more (link opens a new window)'}
        self.assertEqual(predict.match_focus(self.links(), event)['ix'], 2)

    def test_a_tree_that_does_not_hold_the_dom_node_yet_is_waited_for_and_not_guessed_at(self):
        event = {'tag': 'a', 'id': None, 'names': ['Read more (link opens a new window)'], 'backendNodeId': 99}
        self.assertIsNone(predict.match_focus(self.links(), event, last_resort=False))
        self.assertEqual(predict.match_focus(self.links(), event, last_resort=True)['ix'], 1)      # the last try is a guess from the names, as it was

    def test_the_extensions_tree_has_no_dom_node_and_is_matched_by_the_name_and_role_the_browser_computed(self):
        tree = predict.index_children(snap([node(0, 'rootWebArea', kids=[1, 2]), node(1, 'link', 'Home', htmlTag='a'), node(2, 'link', 'Advanced search Link opens in new window', htmlTag='a')], focus=1))
        event = {'tag': 'a', 'id': None, 'names': ['Advanced searchLink opens in new window x'], 'backendNodeId': 7, 'axName': 'Advanced search Link opens in new window', 'axRole': 'link'}
        self.assertEqual(predict.match_focus(tree, event, last_resort=False)['ix'], 2)
        self.assertIsNone(predict.match_focus(tree, dict(event, axRole='button'), last_resort=False))

    def test_of_several_nodes_the_browser_names_the_same_the_tree_has_focused_wins(self):
        event = {'tag': 'a', 'id': None, 'names': [], 'backendNodeId': 7, 'axName': 'Read more (link opens a new window)', 'axRole': 'link'}
        two = predict.index_children(snap([node(0, 'rootWebArea', kids=[1, 2]), node(1, 'link', 'Read more (link opens a new window)', htmlTag='a'), node(2, 'link', 'Read more (link opens a new window)', htmlTag='a')], focus=2))
        self.assertEqual(predict.match_focus(two, event)['ix'], 2)

    def test_where_the_browser_could_not_be_asked_the_names_are_still_a_guess_that_ignores_where_the_lines_broke(self):
        tree = predict.index_children(snap([node(0, 'rootWebArea', kids=[1]), node(1, 'link', 'Read the guidance on accuracy (link opens a new window)', htmlTag='a')], focus=0))
        self.assertEqual(predict.match_focus(tree, {'tag': 'a', 'id': None, 'names': ['Read the guidance on accuracy(link opens a new window)']})['ix'], 1)
        self.assertIsNone(predict.match_focus(tree, {'tag': 'a', 'id': None, 'names': ['Something else']}))


class DocumentAddress(unittest.TestCase):
    def test_the_address_is_the_documents_as_of_the_tree_and_not_the_web_areas_from_when_it_was_made(self):
        s = snap([node(0, 'rootWebArea', url='http://x/a', docUrl='http://x/a?step=2')])
        self.assertEqual(predict.address_of(s), 'http://x/a?step=2')
        self.assertEqual(predict.address_of(snap([node(0, 'rootWebArea', url='http://x/a')])), 'http://x/a')
        self.assertEqual(predict.address_of(snap([node(0, 'rootWebArea')])), 'http://x/')

    def test_the_emulator_is_given_the_document_with_that_address_and_the_tree_itself_is_not_changed(self):
        s = snap([node(0, 'rootWebArea', url='http://x/a', docUrl='http://x/a?step=2', kids=[1]), node(1, 'link', 'Next', url='http://x/a?step=2')]); s['sel'] = {}
        nodes, focus = predict.SnapshotSession(s).dump()
        self.assertEqual((nodes[0]['url'], nodes[1]['name'], focus), ('http://x/a?step=2', 'Next', 0))
        self.assertEqual(s['nodes'][0]['url'], 'http://x/a')


class Order(unittest.TestCase):
    def test_snapshots_come_out_in_the_order_they_were_made(self):
        o = main.Ordered()
        o.add({'seq': 5}, 0); o.add({'seq': 7}, 0); o.add({'seq': 6}, 0)
        self.assertEqual([s['seq'] for s in o.ready(0)], [5, 6, 7])

    def test_one_that_is_late_is_waited_for_and_then_given_up(self):
        o = main.Ordered()
        o.add({'seq': 1}, 0); o.add({'seq': 3}, 0)
        self.assertEqual([s['seq'] for s in o.ready(0)], [1])
        self.assertEqual([s['seq'] for s in o.ready(main.REORDER_WAIT + 1)], [3])
        self.assertEqual(o.lost, 1)

    def test_a_restart_of_the_extension_starts_the_count_again(self):
        o = main.Ordered()
        o.add({'seq': 40}, 0); o.ready(0); o.reset(); o.add({'seq': 1}, 0)
        self.assertEqual([s['seq'] for s in o.ready(0)], [1])


class WebSocketServer(threading.Thread):
    """Enough of a server to answer the handshake and echo each text message back, and to ping first."""
    def __init__(self):
        super().__init__(daemon=True); self.sock = socket.socket(); self.sock.bind(('127.0.0.1', 0)); self.sock.listen(1); self.port = self.sock.getsockname()[1]; self.seen_masked = []

    def run(self):
        conn, _ = self.sock.accept()
        request = b''
        while b'\r\n\r\n' not in request: request += conn.recv(4096)
        key = [l.split(b': ')[1] for l in request.split(b'\r\n') if l.lower().startswith(b'sec-websocket-key')][0]
        accept = base64.b64encode(hashlib.sha1(key + wsclient.GUID.encode()).digest())
        conn.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + b'\r\n\r\n')
        conn.sendall(bytes([0x89, 0]))      # a ping, which the client must answer without handing it on
        while True:
            head = conn.recv(2)
            if not head: return
            n = head[1] & 0x7F; self.seen_masked.append(bool(head[1] & 0x80))
            if n == 126: n = struct.unpack('>H', conn.recv(2))[0]
            elif n == 127: n = struct.unpack('>Q', conn.recv(8))[0]
            mask = conn.recv(4) if head[1] & 0x80 else b'\0\0\0\0'
            data = b''
            while len(data) < n: data += conn.recv(n - len(data))
            if head[0] & 0x0F == 0xA: continue
            text = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            half = len(text) // 2
            conn.sendall(bytes([0x01]) + self.length(half) + text[:half] + bytes([0x80]) + self.length(len(text) - half) + text[half:])      # in two frames

    @staticmethod
    def length(n): return bytes([n]) if n < 126 else bytes([126]) + struct.pack('>H', n) if n < 65536 else bytes([127]) + struct.pack('>Q', n)


class WebSocketClient(unittest.TestCase):
    def test_messages_of_every_length_survive_a_round_trip_and_the_client_masks_what_it_sends(self):
        server = WebSocketServer(); server.start()
        ws = wsclient.WebSocket(f'ws://127.0.0.1:{server.port}/devtools/browser/x')
        for n in (0, 5, 125, 126, 300, 65535, 65536, 70000):
            text = ('é' * n)[:n] if n < 5 else 'x' * n
            ws.send(text)
            self.assertEqual(ws.recv(), text)
        self.assertTrue(all(server.seen_masked))
        ws.close()


if __name__ == '__main__': unittest.main()
