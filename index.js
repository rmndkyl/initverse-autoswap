const { ethers } = require("ethers");
const fs = require('fs');
const chalk = require('chalk');

// Configuration Constants
const CONFIG = {
    TOTAL_TRANSACTIONS: 144,
    DELAY_MINUTES: 10,
    SWAP_AMOUNT: "0.001",
    RPC_URL: "https://rpc-testnet.inichain.com",
    ROUTER_ADDRESS: "0x4ccB784744969D9B63C15cF07E622DDA65A88Ee7",
    TOKEN_PATHS: [
        "0xfbecae21c91446f9c7b87e4e5869926998f99ffe",
        "0xcf259bca0315c6d32e877793b6a10e97e7647fde"
    ],
    SLIPPAGE: 15,
    GAS_LIMIT: 300000,
    DEADLINE_MINUTES: 20,
    ACCOUNT_DELAY_MINUTES: 5 // Delay between switching accounts
};

// Contract ABI
const ROUTER_ABI = [
    "function swapExactETHForTokens(uint256 amountOutMin, address[] path, address to, uint256 deadline) payable",
    "function getAmountsOut(uint256 amountIn, address[] path) view returns (uint256[] amounts)"
];

// ASCII Art Banner
const BANNER = {
    logo: [
        '==============================================================================================',
        '██╗░░░░░░█████╗░██╗░░░██╗███████╗██████╗░  ░█████╗░██╗██████╗░██████╗░██████╗░░█████╗░██████╗░',
        '██║░░░░░██╔══██╗╚██╗░██╔╝██╔════╝██╔══██╗  ██╔══██╗██║██╔══██╗██╔══██╗██╔══██╗██╔══██╗██╔══██╗',
        '██║░░░░░███████║░╚████╔╝░█████╗░░██████╔╝  ███████║██║██████╔╝██║░░██║██████╔╝██║░░██║██████╔╝',
        '██║░░░░░██╔══██║░░╚██╔╝░░██╔══╝░░██╔══██╗  ██╔══██║██║██╔══██╗██║░░██║██╔══██╗██║░░██║██╔═══╝░',
        '██║░░░░░██║░░██║░░░██║░░░███████╗██║░░██║  ██║░░██║██║██║░░██║██████╔╝██║░░██║╚█████╔╝██║░░░░░',
        '╚══════╝╚═╝░░╚═╝░░░╚═╝░░░╚══════╝╚═╝░░╚═╝  ╚═╝░░╚═╝╚═╝╚═╝░░╚═╝╚═════╝░╚═╝░░╚═╝░╚════╝░╚═╝░░░░░',
        '=============================================================================================='
    ],
    info: [
        'community Telegram channel: https://t.me/layerairdrop',
        'community Telegram group: https://t.me/layerairdropdiskusi',
        '==============================================',
        'INITVERSE SCRIPT AUTO SWAP (MULTI-ACCOUNT)',
        '\ncreated by: https://github.com/rmndkyl',
        '=============================================='
    ]
};

// Utility Functions
async function sleep(minutes) {
    return new Promise(resolve => setTimeout(resolve, minutes * 60 * 1000));
}

async function countdown(minutes, message = 'Next transaction') {
    const totalSeconds = minutes * 60;
    for (let i = totalSeconds; i > 0; i--) {
        process.stdout.clearLine();
        process.stdout.cursorTo(0);
        const mins = Math.floor(i / 60);
        const secs = i % 60;
        process.stdout.write(
            chalk.cyan(`${message} in: ${chalk.bold(mins)}m ${chalk.bold(secs)}s`)
        );
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
    console.log('\n');
}

function getFormattedDateTime() {
    return new Date().toLocaleString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
}

function displayBanner() {
    BANNER.logo.forEach(line => console.log(chalk.cyan(line)));
    BANNER.info.forEach(line => console.log(chalk.cyanBright(line)));
}

function loadAccounts() {
    try {
        const data = fs.readFileSync('JS_privateKeys.json', 'utf-8');
        const accounts = JSON.parse(data);
        
        if (!Array.isArray(accounts)) {
            throw new Error('JS_privateKeys.json must contain an array of account objects');
        }
        
        accounts.forEach((acc, index) => {
            if (!acc.privateKey || !acc.address) {
                throw new Error(`Invalid account format at index ${index}`);
            }
        });
        
        return accounts;
    } catch (error) {
        console.error(chalk.red('Error loading JS_privateKeys.json:'), error.message);
        process.exit(1);
    }
}

// Single Swap Function
async function performSingleSwap(contract, walletAddress, accountIndex, transactionIndex) {
    console.log(chalk.cyan(`\n[Account ${accountIndex + 1}] Current Time:`, getFormattedDateTime()));
    console.log(chalk.magenta(`[Account ${accountIndex + 1}] Transaction Progress: ${transactionIndex + 1}/${CONFIG.TOTAL_TRANSACTIONS}`));

    try {
        const swapAmountWei = ethers.parseEther(CONFIG.SWAP_AMOUNT);
        const amountsOut = await contract.getAmountsOut(swapAmountWei, CONFIG.TOKEN_PATHS);
        const amountOutMin = ((amountsOut[1] * BigInt(100 - CONFIG.SLIPPAGE)) / 100n).toString();
        const deadline = Math.floor(Date.now() / 1000) + (CONFIG.DEADLINE_MINUTES * 60);

        const tx = await contract.swapExactETHForTokens(
            amountOutMin,
            CONFIG.TOKEN_PATHS,
            walletAddress,
            deadline,
            {
                value: swapAmountWei,
                gasLimit: CONFIG.GAS_LIMIT
            }
        );

        console.log(chalk.green(`[Account ${accountIndex + 1}] Transaction sent:`, tx.hash));
        console.log(chalk.blue(`[Account ${accountIndex + 1}] Amount:`, CONFIG.SWAP_AMOUNT, "INIT"));

        const receipt = await tx.wait();
        console.log(chalk.green(`[Account ${accountIndex + 1}] Transaction confirmed! Gas used:`, receipt.gasUsed.toString()));
    } catch (error) {
        console.error(chalk.red(`[Account ${accountIndex + 1}] Transaction ${transactionIndex + 1} failed:`), error.message);
    }
}

// Account Swap Handler
async function handleAccountSwaps(wallet, walletAddress, accountIndex, totalAccounts) {
    const contract = new ethers.Contract(CONFIG.ROUTER_ADDRESS, ROUTER_ABI, wallet);
    console.log(chalk.yellow(`\n[Account ${accountIndex + 1}/${totalAccounts}] Starting transactions`));
    console.log(chalk.yellow(`[Account ${accountIndex + 1}] Wallet Address:`, walletAddress));

    for (let i = 0; i < CONFIG.TOTAL_TRANSACTIONS; i++) {
        await performSingleSwap(contract, walletAddress, accountIndex, i);
        
        if (i < CONFIG.TOTAL_TRANSACTIONS - 1) {
            await sleep(CONFIG.DELAY_MINUTES);
        }
    }
}

// Main Multi-Account Concurrent Function
async function runConcurrentSwaps() {
    displayBanner();
    
    const accounts = loadAccounts();
    const provider = new ethers.JsonRpcProvider(CONFIG.RPC_URL);
    
    console.log(chalk.green('\n=== Concurrent Multi-Account Swap Script Started ==='));
    console.log(chalk.yellow(`Total Accounts: ${accounts.length}`));

    // Create an array of promises for each account
    const accountPromises = accounts.map((account, index) => {
        const wallet = new ethers.Wallet(account.privateKey, provider);
        return handleAccountSwaps(wallet, account.address, index, accounts.length);
    });

    // Run all accounts concurrently
    try {
        await Promise.all(accountPromises);
        console.log(chalk.green("\n=== All accounts processed successfully ==="));
    } catch (error) {
        console.error(chalk.red("\nScript execution error:"), error.message);
    }
}

// Script Execution
runConcurrentSwaps()
    .then(() => {
        console.log(chalk.green("\n=== Script completed ==="));
        process.exit(0);
    })
    .catch(error => {
        console.error(chalk.red("\nFatal error:"), error.message);
        process.exit(1);
    });
