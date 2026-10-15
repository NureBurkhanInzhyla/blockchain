from wallet import Transaction
import hashlib
import json
import time
import os 


class Block:
    def __init__(self, index: int, prev_block_hash: str, transactions: list[Transaction], difficulty: int, nonce: int=0):
        self.index = index
        self.timestamp = round(time.time(), 4)

        self.prev_block_hash = prev_block_hash

        self.transactions = transactions
        self.difficulty = difficulty
        self.nonce = nonce

        hashes = [hashlib.sha256(tx.serialize()).hexdigest() for tx in self.transactions]
        self.merkle_root = self.get_merkle_root(hashes)

        self.hash = self.calculate_hash()

    def to_dict(self):
        return {
        "index": self.index,
        "timestamp": self.timestamp,
        "prev_block_hash": self.prev_block_hash,
        "merkle_root": self.merkle_root,
        "difficulty": self.difficulty,
        "nonce": self.nonce,
        "transactions": [tx.to_dictionary() for tx in self.transactions],
        "hash": self.hash
    }

    def calculate_hash(self):
        header = self.get_header()
        return hashlib.sha256(header.encode('utf-8')).hexdigest()

    def get_header(self):
        return f"{self.index}{self.timestamp}{self.prev_block_hash}{self.merkle_root}{self.difficulty}{self.nonce}"


    def get_merkle_root(self, hashes: list[str]):
        if not hashes:
            return hashlib.sha256(b"").hexdigest()

        row = hashes.copy()

        while len(row) > 1:
            if len(row) % 2 != 0:
                row.append(row[-1])

            next_row = []
            for i in range(0, len(row), 2):
                pair = row[i] + row[i+1]
                pair_hash = hashlib.sha256(pair.encode('utf-8')).hexdigest()
                next_row.append(pair_hash)
            
            row = next_row

        return row[0]

    def mine_block(self):
        target = "0" * self.difficulty

        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self.calculate_hash()

    def get_index(self):
        return self.index


       
class Mempool:
    def __init__(self):
        self.pending_transactions = []

    def add_transaction(self, transaction: Transaction, blockchain):
        if transaction.amount <= 0 or transaction.fee < 0:
            raise ValueError("Declined! Zero/Negative values in amount or fee!")

        if not transaction.verify_signature():
            raise ValueError("Declined! Wrong signature!")

        for pending_transaction in self.pending_transactions:
            if transaction.signature == pending_transaction.signature:
                raise ValueError("Declined! This transaction already is pending!")

        if blockchain.has_transaction(transaction):
            raise ValueError("Declined! Transaction already exists in chain!")

        blockchain_balance = blockchain.get_balance(transaction.sender)
        spent_in_mempool = sum(tx.amount + tx.fee for tx in self.pending_transactions if tx.sender == transaction.sender)
        overall_balance = blockchain_balance - spent_in_mempool
       
        if overall_balance < (transaction.amount + transaction.fee):
            raise ValueError("Declined! Not enough money!")

        last_nonce = blockchain.get_last_nonce(transaction.sender)
        
        pending_nonces = [
            pending_tx.nonce
            for pending_tx in self.pending_transactions 
            if pending_tx.sender == transaction.sender
        ]

        if pending_nonces:
            last_nonce = max(last_nonce, max(pending_nonces))

        expected_nonce = last_nonce + 1

        if transaction.nonce != expected_nonce:
            raise ValueError(f"Declined! Invalid nonce! Expected {expected_nonce}, got {transaction.nonce}")

        self.pending_transactions.append(transaction)

    def get_pending_transactions(self, transactions_per_block: int):
        sorted_transactions = sorted(
            self.pending_transactions,
            key=lambda tx: (-tx.fee, tx.nonce)
        )
        return sorted_transactions[:transactions_per_block]

    def remove_transactions(self, mined_transactions: list[Transaction]):
        mined_signatures = {tx.signature for tx in mined_transactions if tx.signature}
        self.pending_transactions = [
            tx for tx in self.pending_transactions
            if tx.signature not in mined_signatures
        ]


class Blockchain:
    def __init__(self, target_block_time: float = 10.0, k: int = 10, file: str = "blockhain.json",  transactions_per_block: int=10, diffuclty: int=2):
        self.storage_file = file
        self.chain = []
        self.current_difficulty = diffuclty
        self.target_block_time = target_block_time
        self.k = k
        self.block_reward = 10.0
        self.transactions_per_block = transactions_per_block

        if not self.load_from_file():
            self.create_genesis_block()


    def save_to_file(self):
        if not self.storage_file:
            return
        
        chain_data = [block.to_dict() for block in self.chain]
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(chain_data, f, indent=4, ensure_ascii=False)
        print(f"Blockchain saved to '{self.storage_file}'.")


    def load_from_file(self) -> bool:
        if not self.storage_file or not os.path.exists(self.storage_file):
            return False

        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                chain_data = json.load(f)

            loaded_chain = []
            for block_dict in chain_data:
                transactions = [
                    Transaction.from_dict(tx_dict) 
                    for tx_dict in block_dict["transactions"]
                ]
                
                block = Block(
                    index=block_dict["index"],
                    prev_block_hash=block_dict["prev_block_hash"],
                    transactions=transactions,
                    difficulty=block_dict["difficulty"],
                    nonce=block_dict["nonce"]
                )
                block.timestamp = block_dict["timestamp"]
                block.prev_block_hash = block_dict["prev_block_hash"]
                block.merkle_root = block_dict["merkle_root"]
                block.hash = block_dict["hash"]

                loaded_chain.append(block)

            self.chain = loaded_chain
            if not self.validate_chain():
                print("Warning: Loaded chain is invalid! Resetting to Genesis.")
                self.chain = []
                return False

            print(f"Successfully loaded {len(self.chain)} blocks from '{self.storage_file}'.")
            return True

        except Exception as e:
            print(f"Failed to load blockchain from file: {e}")
            self.chain = []
            return False


    def create_genesis_block(self):
        genesis_block = Block(index=0, prev_block_hash="0"*64, transactions=[], difficulty=self.current_difficulty)
        genesis_block.mine_block()
        self.add_block(genesis_block)

    def add_block(self, block: Block):
        if len(self.chain) == 0:
            self.chain.append(block)
            self.save_to_file()
            return True

        if not self.validate_block(block, self.chain[-1]):
            print(f"Error! Block №{block.index} is invalid!")
            return False

        self.chain.append(block)
        self.adjust_difficulty()
        self.save_to_file()
        return True

    def get_last_block(self) -> Block:
        return self.chain[-1]

    def get_last_nonce(self, address: str):
        last_nonce = 0
        for block in self.chain:
                for tx in block.transactions:
                    if tx.sender == address and tx.nonce > last_nonce:
                        last_nonce = tx.nonce
        return last_nonce

    def get_balance(self, address: str):
        balance = 0.0
        for block in self.chain:
            for tx in block.transactions:
                if tx.recipient == address:
                    balance += tx.amount
                if tx.sender == address:
                    balance -= (tx.amount + tx.fee)
        return balance

    def has_transaction(self, transaction: Transaction):
        for block in self.chain:
            for tx in block.transactions:
                if tx.signature and tx.signature == transaction.signature:
                    return True
            
        return False

    def adjust_difficulty(self):
        if len(self.chain) < self.k or len(self.chain) % self.k != 0:
            return

        latest_block = self.chain[-1]
        first_block = self.chain[-self.k]

        actual_time = latest_block.timestamp - first_block.timestamp
        expected_time = self.k * self.target_block_time

        if actual_time <= 0:
            return

        ratio = expected_time / actual_time
        ratio = max(0.25, min(ratio, 2.0))

        new_difficulty = self.current_difficulty * ratio

        self.current_difficulty = max(1, round(new_difficulty))

        print(
            f"Difficulty adjusted: "
            f"{self.current_difficulty} "
            f"(actual: {actual_time:.2f}s, "
            f"expected: {expected_time:.2f}s)"
        )

    def validate_block(self, block, prev_block):
        if block.calculate_hash() != block.hash:
            print(f"Hash of block nr. {block.index} is incorrect!")
            return False

        if prev_block is not None:
            if block.prev_block_hash != prev_block.hash:
                print(f"Hash of previous block is incorrect!")
                return False
        elif block.prev_block_hash != "0" * 64:
                print(f"Hash of previous block is incorrect!")
                return False

        tx_hashes = [
            hashlib.sha256(tx.serialize()).hexdigest()
            for tx in block.transactions
        ]

        calculated_merkle_root = block.get_merkle_root(tx_hashes)

        if calculated_merkle_root != block.merkle_root:
            print(f"Error! Merkle root is incorrect!")
            return False

        target = "0" * block.difficulty
        if not block.hash.startswith(target):
            print(f"Hash of the block starts not with target amount of '0'!")
            return False


        for transaction in block.transactions:
            if transaction.sender == "0" * 64:
                continue

            if not hasattr(transaction, "signature") or not transaction.signature:
                print(f"Signature is missing!")
                return False

            try:
                if not transaction.verify_signature():
                    print(f"Signature is not verified!")
                    return False
            except Exception as e:
                print(f"Error during signature verification: {e}")
                return False

        return True


    def validate_chain(self):
        if not self.chain:
            return False

        nonces = {}
        balances = {}

        for i in range(len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1] if i > 0 else None

            if previous_block is not None and current_block.index != previous_block.index + 1:
                print(f"Error! Block #{current_block.index} has wrong index sequence!")
                return False

            if not self.validate_block(current_block, previous_block):
                print(f"Error! Block №{current_block.index} is incorrect!")
                return False


            rewards_count = 0
            for transaction in current_block.transactions:
                if transaction.sender == "0" * 64:
                    rewards_count += 1

                    if rewards_count > 1:
                        print(f"Error: Multiple reward transactions in block nr.{current_block.index}!")
                        return False
                
                    total_fees = sum(
                        tx.fee 
                        for tx in current_block.transactions 
                        if tx.sender != "0" * 64
                    )

                    if transaction.amount > (total_fees + self.block_reward):
                        print(f"Error! Miner reward in block nr.{current_block.index} is more than allowed!") 
                        return False

                    balances[transaction.recipient] = balances.get(transaction.recipient, 0.0) + transaction.amount
                    continue
              
                sender = transaction.sender
                recipient = transaction.recipient
                total_spent = transaction.amount + transaction.fee

                expected_nonce = nonces.get(sender, 0) + 1
                if transaction.nonce != expected_nonce:
                    print("Wrong transaction nonce!")
                    return False
                
                nonces[sender] = transaction.nonce

                current_sender_balance = balances.get(sender, 0.0)
                if current_sender_balance < total_spent:
                    print("Sender does not have enough balance!")
                    return False

                balances[sender] = current_sender_balance - total_spent
                balances[recipient] = balances.get(recipient, 0.0) + transaction.amount

        return True

    def mine_pending_transactions(self, miner_adr: str, mempool):
        mempool_transactions = mempool.get_pending_transactions(self.transactions_per_block)
        total_fees = sum(transaction.fee for transaction in mempool_transactions)

        reward = Transaction(
            sender="0" * 64,
            recipient=miner_adr,
            amount=self.block_reward + total_fees,
            fee=0.0,
            nonce=0,
            sender_public_key=""
        )

        block_transactions = [reward] + mempool_transactions
        prev_block = self.get_last_block()

        new_block = Block(
            index=prev_block.get_index() + 1,
            prev_block_hash=prev_block.hash,
            transactions=block_transactions,
            difficulty=self.current_difficulty,
        )

        new_block.mine_block()

        self.chain.append(new_block)

        mempool.remove_transactions(mempool_transactions)

        self.adjust_difficulty()


    def calculate_total_work(self, chain: list):
        total_work = 0
        for block in chain:
            total_work += 2 ** block.difficulty

        return total_work

    def replace_chain(self, new_chain: list, mempool: Mempool) -> bool:
        current_work = self.calculate_total_work(self.chain)

        chain = []

        try:
            for block in new_chain:
                if isinstance(block, Block):
                    chain.append(block)
                else:
                    transactions = [Transaction.from_dict(tx) for tx in block.get("transactions", [])]
                    b = Block(
                        index=block["index"],
                        prev_block_hash=block["prev_block_hash"],
                        transactions=transactions,
                        difficulty=block["difficulty"],
                        nonce=block["nonce"]
                    )

                    b.timestamp = block["timestamp"]
                    b.merkle_root = block["merkle_root"]
                    b.hash = block["hash"]

                    chain.append(b)

        except Exception as e:
            print(f"Error parsing received chain: {e}")
            return False

        new_work = self.calculate_total_work(chain)

        if new_work <= current_work:
            print(f"Received chain work ({new_work}) <= current work ({current_work})")
            return False

        temp_blockchain = Blockchain(file=None)
        temp_blockchain.chain = chain

        if not temp_blockchain.validate_chain():
            print("Received chain is invalid!")
            return False

        fork = 0
        transaction_to_mempool = []
        for i in range(min(len(self.chain), len(chain))):
            if self.chain[i].hash == chain[i].hash:
                fork = i
            else:
                break

        new_chain_signatures = {
            tx.signature 
            for b in chain 
            for tx in b.transactions 
            if tx.signature
        }

        mempool_signatures = {
            tx.signature 
            for tx in mempool.pending_transactions 
            if tx.signature
        }

        for block in self.chain[fork + 1:]:
            for tx in block.transactions:
                if tx.sender != "0" * 64 and tx.signature not in new_chain_signatures and tx.signature not in mempool_signatures:
                    transaction_to_mempool.append(tx)

        self.chain = chain
        self.save_to_file()
        for tx in transaction_to_mempool:
            mempool.pending_transactions.append(tx)

        print(f"Chain replaced with longer one succesfully! New length: {len(self.chain)}")

        return True




        



 