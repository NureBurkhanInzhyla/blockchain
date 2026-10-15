from wallet import Transaction, Wallet
from blockchain import Block, Blockchain, Mempool
import hashlib

def attack1():
    walletA = Wallet()
    walletB = Wallet()
    blockchain = Blockchain(file=None)
    mempool = Mempool()

    next_nonce = walletA.get_next_nonce(blockchain, mempool)

    blockchain.mine_pending_transactions(walletA.get_address(), mempool)

    tx = Transaction(walletA.get_address(), walletB.get_address(), 5.0, 1.0, next_nonce, walletA.get_public_key_hex())
    tx.sign(walletA)

    mempool.add_transaction(tx, blockchain)
    blockchain.mine_pending_transactions(walletB.get_address(), mempool)

    blockchain.chain[2].transactions[1].amount = 100.0

    assert blockchain.validate_chain() is False
    print("Replacing transaction amount after submitting succesfuly declined!")


def attack2():
    walletA = Wallet()
    walletB = Wallet()
    blockchain = Blockchain(file=None)
    mempool = Mempool()

    next_nonce = walletA.get_next_nonce(blockchain, mempool)

    blockchain.mine_pending_transactions(walletA.get_address(), mempool)

    tx = Transaction(walletA.get_address(), walletB.get_address(), 5.0, 1.0, next_nonce, walletA.get_public_key_hex())
    tx.sign(walletA)

    mempool.add_transaction(tx, blockchain)
    blockchain.mine_pending_transactions(walletB.get_address(), mempool)
    blockchain.mine_pending_transactions(walletB.get_address(), mempool)

    block2 = blockchain.chain[2]
    block2.transactions[1].amount = 9.0
    block2.transactions[1].verify_signature = lambda: True

    tx_hashes = [hashlib.sha256(t.serialize()).hexdigest() for t in block2.transactions]
    block2.merkle_root = block2.get_merkle_root(tx_hashes)
    block2.nonce = 0
    block2.hash = block2.calculate_hash()
    block2.mine_block()

    assert blockchain.validate_chain() is False
    print("Replacing transaction amount and hashes after submitting succesfuly declined!")

def attack3():
    walletA = Wallet()
    walletB = Wallet()
    blockchain = Blockchain(file=None)
    mempool = Mempool()

    blockchain.mine_pending_transactions(walletA.get_address(), mempool)

    next_nonce = walletA.get_next_nonce(blockchain, mempool)
    tx = Transaction(walletA.get_address(), walletB.get_address(), 5.0, 1.0, next_nonce, walletA.get_public_key_hex())

    try:
        tx.sign(walletB)
        assert False, "Should have been an exception!"
    except ValueError as e:
        assert "You cannot sign someone else's transaction!" in str(e)
    

def attack4():
    walletA = Wallet()
    walletB = Wallet()
    blockchain = Blockchain(file=None)
    mempool = Mempool()

    blockchain.mine_pending_transactions(walletA.get_address(), mempool)

    next_nonce = walletA.get_next_nonce(blockchain, mempool)
    tx1 = Transaction(walletA.get_address(), walletB.get_address(), 5.0, 1.0, next_nonce, walletA.get_public_key_hex())
    tx1.sign(walletA)
    mempool.add_transaction(tx1, blockchain)

    next_nonce2 = walletA.get_next_nonce(blockchain, mempool)
    tx2 = Transaction(walletA.get_address(), walletB.get_address(), 5.0, 1.0, next_nonce2, walletA.get_public_key_hex())
    tx2.sign(walletA)

    try:
        mempool.add_transaction(tx2, blockchain)
        assert False, "Should have been an exception!"
    except ValueError as e:
        assert "Declined! Not enough money!" in str(e)


def attack5():
    walletA = Wallet()
    walletB = Wallet()
    blockchain = Blockchain(file=None)
    mempool = Mempool()

    next_nonce = walletA.get_next_nonce(blockchain, mempool)

    blockchain.mine_pending_transactions(walletA.get_address(), mempool)

    tx = Transaction(walletA.get_address(), walletB.get_address(), 5.0, 1.0, next_nonce, walletA.get_public_key_hex())
    tx.sign(walletA)

    mempool.add_transaction(tx, blockchain)
    blockchain.mine_pending_transactions(walletB.get_address(), mempool)

    try:
        mempool.add_transaction(tx, blockchain)
        assert False, "Should have been an exception!"
    except ValueError as e:
        assert "Declined! Transaction already exists in chain!" in str(e)



if __name__ == "__main__":
    attack1()
    print("attack1 passed!")

    attack2()
    print("attack2 passed!")

    attack3()
    print("attack3 passed!")

    attack4()
    print("attack4 passed!")

    attack5()
    print("attack5 passed!")