import ecdsa
import hashlib
import json

class Wallet:
    def __init__(self):
        self.private_key = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        
        self.public_key = self.private_key.get_verifying_key()

        self.address = hashlib.sha256(self.public_key.to_string()).hexdigest()

    def get_private_key_hex(self):
        return self.private_key.to_string().hex()

    def get_public_key_hex(self):
        return self.public_key.to_string().hex()

    def get_address(self):
        return self.address

    def get_next_nonce(self, blockchain, mempool):
        last_nonce = blockchain.get_last_nonce(self.get_address())
        pending_transactions = mempool.get_pending_transactions(blockchain.transactions_per_block)

        nonces_in_mempool = [
            transaction.nonce 
            for transaction in pending_transactions
            if transaction.sender == self.get_address()
        ]
        if nonces_in_mempool:
            last_nonce = max(last_nonce, max(nonces_in_mempool))

        return last_nonce + 1


class Transaction:
    def __init__(self, sender: str, recipient: str, amount: float, fee: float, nonce: int, sender_public_key: str, signature: str=None):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.fee = fee
        self.nonce = nonce
        self.sender_public_key = sender_public_key
        self.signature = signature

    def to_dictionary(self):
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "fee": self.fee,
            "nonce": self.nonce,
            "sender_public_key": self.sender_public_key, 
            "signature": self.signature
        }

    def from_dict(d: dict):
        return Transaction(
            sender=d["sender"],
            recipient=d["recipient"],
            amount=d["amount"],
            fee=d.get("fee", 0.0),
            nonce=d.get("nonce", 0),
            sender_public_key=d.get("sender_public_key", ""),
            signature=d.get("signature", None)
        )

    def serialize(self):
        data = {
            "sender": self.sender,
            "recipient": self.recipient,
            "amount": self.amount,
            "fee": self.fee,
            "nonce": self.nonce,
            "sender_public_key": self.sender_public_key
        }
        return json.dumps(data, sort_keys=True).encode('utf-8')


    def sign(self, wallet: Wallet):
        if wallet.address != self.sender:
            raise ValueError("You cannot sign someone else's transaction!")

        signature = wallet.private_key.sign(self.serialize())
        self.signature = signature.hex()

    def verify_signature(self):
        if self.sender == "0" * 64:
            return True

        if not self.signature or not self.sender_public_key:
            return False

        try:
            pub_key_bytes = bytes.fromhex(self.sender_public_key)
            address = hashlib.sha256(pub_key_bytes).hexdigest()
            if address != self.sender:
                return False

            verifying_key = ecdsa.VerifyingKey.from_string(pub_key_bytes, curve=ecdsa.SECP256k1)
            signature_bytes = bytes.fromhex(self.signature)
            return verifying_key.verify(signature_bytes, self.serialize()) 
        
        except (ecdsa.BadSignatureError, Exception):
            return False



