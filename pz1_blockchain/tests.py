from datetime import timedelta
import hashlib
from wallet import Transaction, Wallet
from blockchain import Block, Mempool, Blockchain
import os
import time

def test_odd_merkle_root():
    transaction1 = Transaction("aaa11", "bbb22", 10.0, 1.0, 1, "pbkey1")
    transaction2 = Transaction("bbb22", "ccc33", 20.0, 5.0, 1, "pbkey2")
    transaction3 = Transaction("ccc33", "ddd44", 5.0, 0.5, 1 , "pbkey3")

    transactions = [transaction1, transaction2, transaction3]

    hashes = [hashlib.sha256(tx.serialize()).hexdigest() for tx in transactions]
    pair1 = hashlib.sha256((hashes[0] + hashes[1]).encode('utf-8')).hexdigest()
    pair2 = hashlib.sha256((hashes[2] + hashes[2]).encode('utf-8')).hexdigest()

    expected = hashlib.sha256((pair1 + pair2).encode('utf-8')).hexdigest()

    block = Block(1, None, transactions, difficulty=2)

    print(f"Actual root: {block.merkle_root}")
    print(f"Expected root:  {expected}")
    
    assert block.merkle_root == expected, "Root was not calculated right for odd transactions!"

def test_even_merkle_root():
    transaction1 = Transaction("aaa11", "bbb22", 10.0, 1.0, 1, "pbkey1")
    transaction2 = Transaction("bbb22", "ccc33", 20.0, 5.0, 1, "pbkey2")
    transaction3 = Transaction("ccc33", "ddd44", 5.0, 0.5, 1 , "pbkey3")
    transaction4 = Transaction("ddd44", "aaa11", 15.0, 2.0, 1 , "pbkey4")

    transactions = [transaction1, transaction2, transaction3, transaction4]

    hashes = [hashlib.sha256(tx.serialize()).hexdigest() for tx in transactions]
    pair1 = hashlib.sha256((hashes[0] + hashes[1]).encode('utf-8')).hexdigest()
    pair2 = hashlib.sha256((hashes[2] + hashes[3]).encode('utf-8')).hexdigest()

    expected = hashlib.sha256((pair1 + pair2).encode('utf-8')).hexdigest()

    block = Block(1, None, transactions, difficulty=2)

    print(f"Actual root: {block.merkle_root}")
    print(f"Expected root:  {expected}")
    
    assert block.merkle_root == expected, "Root was not calculated right for even transactions!"


def test_valid_transaction_signature():
    wallet = Wallet()
    tx = Transaction(wallet.get_address(), "recipient_address", 10.0, 1.0, 1, wallet.get_public_key_hex())
    tx.sign(wallet)

    assert tx.verify_signature() is True

def test_invalid_transaction_signature():
    wallet = Wallet()
    tx = Transaction(wallet.get_address(), "recipient_address", 10.0, 1.0, 1, wallet.get_public_key_hex())
    tx.sign(wallet)

    tx.amount = 100.0

    assert tx.verify_signature() is False


def test_not_enough_money():
    wallet = Wallet()
    mempool = Mempool()
    blockchain = Blockchain(file=None)

    transaction = Transaction(wallet.get_address(), "recipient", 10.0, 1.0, 1, wallet.get_public_key_hex())
    transaction.sign(wallet)

    try:
        mempool.add_transaction(transaction, blockchain)
        assert False, "Should have been an exception!"
    except ValueError as e:
        assert "Declined! Not enough money!" in str(e)


def test_invalid_transaction_amount():
    wallet = Wallet()
    mempool = Mempool()
    blockchain = Blockchain(file=None)

    blockchain.mine_pending_transactions(wallet.get_address(), mempool)

    transaction = Transaction(wallet.get_address(), "recipient", -10.0, 1.0, 0, wallet.get_public_key_hex())
    transaction.sign(wallet)

    try:
        mempool.add_transaction(transaction, blockchain)
        assert False, "Should have thrown an exception for negative amount!"
    except ValueError as e:
        assert "Declined! Zero/Negative values in amount or fee!" in str(e)


def test_save_and_load_blockchain():
    filename = "test_temp_storage.json"
    if os.path.exists(filename):
        os.remove(filename)

    bc1 = Blockchain(file=filename)
    mempool = Mempool()
    bc1.mine_pending_transactions("miner_address", mempool)
    bc1.save_to_file()

    bc2 = Blockchain(file=filename)
    assert len(bc2.chain) == len(bc1.chain)
    assert bc2.chain[-1].hash == bc1.chain[-1].hash

    if os.path.exists(filename):
        os.remove(filename)


def test_balance():
    blockchain = Blockchain(file=None)
    mempool = Mempool()
    wallet1, wallet2 = Wallet(), Wallet()

    assert blockchain.get_balance(wallet1.get_address()) == 0.0
    assert blockchain.get_balance(wallet2.get_address()) == 0.0

    blockchain.mine_pending_transactions(wallet1.get_address(), mempool)
    assert blockchain.get_balance(wallet1.get_address()) == 10.0

    tx = Transaction(wallet1.get_address(), wallet2.get_address(), 3.0, 1.0, 1, wallet1.get_public_key_hex())
    tx.sign(wallet1)
    mempool.add_transaction(tx, blockchain)

    blockchain.mine_pending_transactions(wallet1.get_address(), mempool)

    assert blockchain.get_balance(wallet1.get_address()) == 17.0
    
    assert blockchain.get_balance(wallet2.get_address()) == 3.0


def test_chain_fork():
    walletA = Wallet()
    walletB = Wallet()
    walletC = Wallet()

    node1_chain = Blockchain(file=None)
    node2_chain = Blockchain(file=None)

    node1_mempool = Mempool()
    node2_mempool = Mempool()

    node1_chain.mine_pending_transactions(walletA.get_address(), node1_mempool)
    node1_chain.mine_pending_transactions(walletA.get_address(), node1_mempool)

    node2_chain.chain = [Block(
        index=b.index,
        prev_block_hash=b.prev_block_hash,
        transactions=b.transactions,
        difficulty=b.difficulty,
        nonce=b.nonce
    ) for b in node1_chain.chain]
    for i, b in enumerate(node1_chain.chain):
        node2_chain.chain[i].timestamp = b.timestamp
        node2_chain.chain[i].merkle_root = b.merkle_root
        node2_chain.chain[i].hash = b.hash

    assert len(node1_chain.chain) == 3
    assert node1_chain.get_last_block().hash == node2_chain.get_last_block().hash

    transaction1 = Transaction(
        sender=walletA.get_address(),
        recipient=walletC.get_address(),
        amount=5.0,
        fee=0.5,
        nonce=1,
        sender_public_key=walletA.get_public_key_hex()        
    )
    transaction1.sign(walletA)
    node1_mempool.add_transaction(transaction1, node1_chain)

    node1_chain.mine_pending_transactions(walletA.get_address(), node1_mempool)

    node2_chain.mine_pending_transactions(walletB.get_address(), node2_mempool)
    node2_chain.mine_pending_transactions(walletB.get_address(), node2_mempool)

    assert node1_chain.chain[3].hash != node2_chain.chain[3].hash

    new_chain_result = node2_chain.replace_chain(node1_chain.chain, node2_mempool)

    assert new_chain_result is False
    print("Node 2 succesfully declined not correct chain from node 1.")

    new_chain_result = node1_chain.replace_chain(node2_chain.chain, node1_mempool)

    assert new_chain_result is True
    assert len(node1_chain.chain) == len(node2_chain.chain)
    assert node1_chain.get_last_block().hash == node2_chain.get_last_block().hash
    print("Succesfully replaced chain in node 1 with correct chain from node 2!")

    mempool_signatures = [tx.signature for tx in node1_mempool.pending_transactions]
    
    assert transaction1.signature in mempool_signatures
    print("Transaction1 succesfully returned to mempool!")


def test_difficulty_increase():
    blockchain = Blockchain(target_block_time=10.0, k=3, file=None)
    start_difficulty = blockchain.current_difficulty

    now = time.time()
    for i in range(1,4):
        prev_block = blockchain.get_last_block()
        new_block = Block(
            index=i,
            prev_block_hash=prev_block.hash,
            transactions=[],
            difficulty=blockchain.current_difficulty,
        )
        new_block.timestamp = now + 1
        new_block.mine_block()
        blockchain.add_block(new_block)

    assert blockchain.current_difficulty > start_difficulty
    print(f"Start difficulty: {start_difficulty}, New difficulty: {blockchain.current_difficulty}")
    print("Difficulty was succesfully adjusted!")


def test_reward_validation():
    wallet = Wallet()
    blockchain = Blockchain(file=None)
    mempool = Mempool()
    blockchain.mine_pending_transactions(wallet.get_address(), mempool)
    assert blockchain.get_balance(wallet.get_address()) == 10

    blockchain.chain[-1].transactions[0].amount = 1000

    assert blockchain.validate_chain() is False

def test_block_size_limit_and_fee_sorting():
    walletA = Wallet()
    walletB = Wallet()
    walletC = Wallet()
    blockchain = Blockchain(transactions_per_block=2, file=None)
    mempool = Mempool()

    blockchain.mine_pending_transactions(walletA.get_address(), mempool)

    transaction1 = Transaction(walletA.get_address(), walletB.get_address(), 1.0, fee=0.1, nonce=1, sender_public_key=walletA.get_public_key_hex())
    transaction1.sign(walletA)

    transaction2 = Transaction(walletA.get_address(), walletB.get_address(), 1.0, fee=0.9, nonce=2, sender_public_key=walletA.get_public_key_hex())
    transaction2.sign(walletA)

    transaction3 = Transaction(walletA.get_address(), walletB.get_address(), 1.0, fee=0.5, nonce=3, sender_public_key=walletA.get_public_key_hex())
    transaction3.sign(walletA)

    mempool.add_transaction(transaction1, blockchain)
    mempool.add_transaction(transaction2, blockchain)
    mempool.add_transaction(transaction3, blockchain)

    assert len(mempool.pending_transactions) == 3

    blockchain.mine_pending_transactions(walletA.get_address(), mempool)
    mined_block = blockchain.get_last_block()
    user_transactions = [tx for tx in mined_block.transactions if tx.sender != "0" * 64]
    
    assert len(user_transactions) == 2, f"Expected 2 transactions in block, got {len(user_transactions)}"

    mined_fees = [tx.fee for tx in user_transactions]
    assert 0.9 == mined_fees[0] and 0.5 == mined_fees[1]
    assert 0.1 not in mined_fees
    assert len(mempool.pending_transactions) == 1
    assert mempool.pending_transactions[0].fee == 0.1


if __name__ == "__main__":
    test_odd_merkle_root()
    print("1. test_odd_merkle_root passed!")

    test_even_merkle_root()
    print("2. test_even_merkle_root passed!")

    test_valid_transaction_signature()
    print("3. test_valid_transaction_signature passed!")

    test_invalid_transaction_signature()
    print("4. test_invalid_transaction_signature passed!")

    test_not_enough_money()
    print("5. test_not_enough_money passed!")

    test_invalid_transaction_amount()
    print("6. test_invalid_transaction_amount passed!")

    test_save_and_load_blockchain()
    print("7. test_save_and_load_blockchain passed!")

    test_balance()
    print("8. test_balance passed!")

    test_chain_fork()
    print("9. test_chain_fork passed!")

    test_difficulty_increase()
    print("10. test_difficulty_increase passed!")

    test_reward_validation()
    print("11. test_reward_validation passed!")

    test_block_size_limit_and_fee_sorting()
    print("12. test_block_size_limit_and_fee_sorting passed!")

    print("\nAll tests completed successfully!")