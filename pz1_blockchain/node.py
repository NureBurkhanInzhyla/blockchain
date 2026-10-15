from wallet import Transaction, Wallet
from blockchain import Block, Blockchain, Mempool
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import sys
import requests
import os

app = FastAPI(title="Blockchain Node")

blockchain = Blockchain()
mempool = Mempool()
wallets: dict[str, Wallet] = {}
neighbors = set()

class TransactionDTO(BaseModel):
    sender: str
    recipient: str
    amount: float
    fee: float
    sender_public_key: str
    signature: Optional[str] = None


def send_to_neighbors(endpoint: str, data: dict):
    for neighbor in neighbors:
        try:
            url = f"{neighbor.rstrip('/')}{endpoint}"
            requests.post(url, json=data, timeout=2)
        except Exception:
            pass

def deserialize_block(block: dict):
    transactions = []
    for transaction in block["transactions"]:
        tx = Transaction(
            sender=transaction["sender"],
            recipient=transaction["recipient"],
            amount=transaction["amount"],
            fee=transaction["fee"],
            nonce=transaction["nonce"],
            sender_public_key=transaction["sender_public_key"],
        )

        tx.signature = transaction.get("signature")

        transactions.append(tx)

    deserialized_block = Block(
        index=block["index"],
        prev_block_hash=["prev_block_hash"],
        transactions=transactions,
        difficulty=block["difficulty"],
        nonce=block["nonce"]
    )
    deserialized_block.hash = block["hash"]
    deserialized_block.prev_block_hash = block["prev_block_hash"]
    deserialized_block.timestamp = block["timestamp"]
    deserialized_block.merkle_root = block["merkle_root"]

    return deserialized_block

@app.post("/wallet/create")
def create_wallet():
    wallet = Wallet()
    wallets[wallet.address] = wallet
    return {
        "message": "Wallet created successfully!",
        "address": wallet.address,
        "public_key": wallet.get_public_key_hex(),
        "private_key": wallet.get_private_key_hex()
    }

@app.post("/transaction/send")
def send_transaction(transaction_dto: TransactionDTO):
    next_nonce = wallets[transaction_dto.sender].get_next_nonce(blockchain, mempool)
    transaction = Transaction(
        sender=transaction_dto.sender,
        recipient=transaction_dto.recipient,
        amount=transaction_dto.amount,
        fee=transaction_dto.fee,
        nonce=next_nonce,
        sender_public_key=transaction_dto.sender_public_key
    )

    if transaction_dto.signature:
        transaction.signature = transaction_dto.signature
    elif transaction_dto.sender in wallets:
        transaction.sign(wallets[transaction_dto.sender])
    else:
        raise HTTPException(status_code=400, detail="Signature missing and private key not found on node!")

    try:
        mempool.add_transaction(transaction, blockchain)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


    send_to_neighbors("/p2p/transaction", transaction.to_dictionary())

    return {"message": "Sent succesfully!"}


@app.get("/chain")
def get_chain():
    chain = [block.to_dict() for block in blockchain.chain]
    return {"length": len(chain), "chain": chain}

@app.get("/chain/validate")
def validate_chain():
    is_valid = blockchain.validate_chain()
    return {"is_valid": is_valid}

@app.get("/wallet/balance/{address}")
def get_balance(address: str):
    balance = blockchain.get_balance(address)
    return {
        "address": address,
        "balance": balance
    }

@app.post("/mine")
def mine_block(miner_adr: str):

    blockchain.mine_pending_transactions(miner_adr, mempool)
    mined_block = blockchain.get_last_block()

    block_dict = mined_block.to_dict()
    send_to_neighbors("/p2p/block", block_dict)

    return {"message": f"Block was mined!", "block": block_dict}

@app.post("/neighbor/add")
def add_neighbor(address: str):
    neighbors.add(address.rstrip("/"))
    return {"message": "Node added successfully", "all_neighbors": list(neighbors)}



@app.post("/sync")
def sync_with_network():
    best_candidate_chain = None
    max_work = blockchain.calculate_total_work(blockchain.chain)

    print(f"START SYNC. Сurrent total work: {max_work}")

    for neighbor in list(neighbors):
        try:
            res = requests.get(f"{neighbor.rstrip('/')}/chain", timeout=2)
            if res.status_code == 200:
                data = res.json()
                candidate_raw = data.get("chain", [])

                candidate_blocks = [
                    b if isinstance(b, Block) else Block.from_dict(b)
                    for b in candidate_raw
                ]

                candidate_work = blockchain.calculate_total_work(candidate_blocks)
                print(f"Neighbor {neighbor} work: {candidate_work}")

                if candidate_work > max_work:
                    max_work = candidate_work
                    best_candidate_chain = candidate_blocks

        except Exception as e:
            print(f"Error checking neighbor {neighbor}: {e}")

    if best_candidate_chain:
        if blockchain.replace_chain(best_candidate_chain, mempool):
            return {
                "message": "Chain replaced with the heaviest chain in the network!",
                "new_length": len(blockchain.chain),
                "total_work": max_work
            }

    return {
        "message": "Current chain is already up to date (holds the highest total work).",
        "length": len(blockchain.chain),
        "total_work": max_work
    }


@app.post("/p2p/transaction")
def receive_transaction(data: dict):
    transaction = Transaction(
        sender=data["sender"],
        recipient=data["recipient"],
        amount=data["amount"],
        fee=data["fee"],
        nonce=data["nonce"],
        sender_public_key=data["sender_public_key"]
    )

    transaction.signature = data.get("signature")

    try:
        mempool.add_transaction(transaction, blockchain)
    except Exception:
        return {"status": "ignored"}

    return {"status": "accepted"}


@app.post("/p2p/block")
def receive_block(block: dict):
    new_block = deserialize_block(block)
    last_block = blockchain.get_last_block()

    if new_block.index == last_block.index + 1:
        if blockchain.validate_block(new_block, last_block):
            blockchain.add_block(new_block)
            mempool.remove_transactions(new_block.transactions)
            return {"status": "accepted"}

    elif new_block.index > last_block.index:
        sync_with_network()

    return {"status": "ignored"}




if __name__=="__main__":
    port = int(os.getenv("PORT", sys.argv[1] if len(sys.argv) > 1 else 5001))
    
    uvicorn.run(app, host="0.0.0.0", port=port)