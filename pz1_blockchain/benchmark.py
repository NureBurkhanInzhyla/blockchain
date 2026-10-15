import time
import numpy as np
import matplotlib.pyplot as plt
from blockchain import Blockchain, Mempool
from wallet import Transaction, Wallet

def benchmark_mining():
    difficulties = [1,2,3,4,5]
    runs = 10

    results = {difficulty: [] for difficulty in difficulties}

    for difficulty in difficulties:
        print(f"Test for difficulty {difficulty}")
        for i in range(runs):
            blockchain = Blockchain(file=None, diffuclty=difficulty)
            mempool = Mempool()
            
            walletA = Wallet()
            walletB = Wallet()
            
            blockchain.mine_pending_transactions(walletA.get_address(), mempool)
            
            next_nonce = walletA.get_next_nonce(blockchain, mempool)
            tx = Transaction(
                sender=walletA.get_address(),
                recipient=walletB.get_address(),
                amount=5.0,
                fee=1.0,
                nonce=next_nonce,
                sender_public_key=walletA.get_public_key_hex()
            )
            tx.sign(walletA)
            
            mempool.add_transaction(tx, blockchain)
            
            start_time = time.time()
            blockchain.mine_pending_transactions(walletB.get_address(), mempool)
            elapsed_time = time.time() - start_time
            
            results[difficulty].append(elapsed_time)
            
            print(f"Start #{i+1}: {elapsed_time:.4f} s")


    means = [np.mean(results[d]) for d in difficulties]
    stds = [np.std(results[d]) for d in difficulties]

    print(means)

    plt.figure(figsize=(9, 6))
    
    plt.errorbar(
        difficulties, 
        means, 
        yerr=stds, 
        fmt='-o', 
        color='b', 
        ecolor='r', 
        capsize=5, 
        label='Average time'
    )

    plt.yscale('log')
    
    plt.xticks(difficulties)
    plt.xlabel('Difficulty')
    plt.ylabel('Mining time in seconds')
    plt.title('Dependence of mining time on difficulty')
    plt.grid(True, which="both", ls="--", alpha=0.6)
    plt.legend()
    
    plt.show()

if __name__ == "__main__":
    benchmark_mining()