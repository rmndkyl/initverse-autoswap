const { ethers } = require("ethers");
const fs = require('fs');
const chalk = require('chalk');

// Configuration Constants
const CONFIG = {
    TOTAL_TRANSACTIONS: 144,
    DELAY_MINUTES: 1,
    SWAP_AMOUNT: "0.0001",
    RPC_URL: "https://rpc-testnet.inichain.com",
    ROUTER_ADDRESS: "0x4ccB784744969D9B63C15cF07E622DDA65A88Ee7",
    TOKEN_PATHS: [
        "0xfbecae21c91446f9c7b87e4e5869926998f99ffe",
        "0xcf259bca0315c6d32e877793b6a10e97e7647fde"
    ],
    SLIPPAGE: 10,
    GAS_LIMIT: 300000,
    DEADLINE_MINUTES: 20
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
        'INITVERSE SCRIPT AUTO SWAP',
        '\ncreated by: https://github.com/rmndkyl',
        '=============================================='
    ]
};

// Utility Functions
async function sleep(minutes) {
    return new Promise(resolve => setTimeout(resolve, minutes * 60 * 1000));
}

async function countdown(minutes) {
    const totalSeconds = minutes * 60;
    for (let i = totalSeconds; i > 0; i--) {
        process.stdout.clearLine();
        process.stdout.cursorTo(0);
        const mins = Math.floor(i / 60);
        const secs = i % 60;
        process.stdout.write(
            chalk.cyan(`Next transaction in: ${chalk.bold(mins)}m ${chalk.bold(secs)}s`)
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

// Main Swap Function
async function swapExactETHForTokens() {
    // Read credentials
    let privateKey, walletAddress;
    try {
        [privateKey, walletAddress] = fs.readFileSync('token.txt', 'utf-8').trim().split(',');
    } catch (error) {
        console.error(chalk.red('Error reading token.txt file:'), error.message);
        process.exit(1);
    }

    // Setup provider and contract
    const provider = new ethers.JsonRpcProvider(CONFIG.RPC_URL);
    const wallet = new ethers.Wallet(privateKey, provider);
    const contract = new ethers.Contract(CONFIG.ROUTER_ADDRESS, ROUTER_ABI, wallet);

    // Display initial information
    displayBanner();
    console.log(chalk.green('\n=== Swap Script Started ==='));
    console.log(chalk.yellow('Wallet Address:', walletAddress));
    console.log(chalk.yellow('Total Transactions:', CONFIG.TOTAL_TRANSACTIONS));

    // Execute transactions
    for (let i = 0; i < CONFIG.TOTAL_TRANSACTIONS; i++) {
        try {
            console.log(chalk.cyan('\nCurrent Time:', getFormattedDateTime()));
            console.log(chalk.magenta(`Transaction Progress: ${i + 1}/${CONFIG.TOTAL_TRANSACTIONS}`));

            // Prepare transaction
            const swapAmountWei = ethers.parseEther(CONFIG.SWAP_AMOUNT);
            const amountsOut = await contract.getAmountsOut(swapAmountWei, CONFIG.TOKEN_PATHS);
            const amountOutMin = ((amountsOut[1] * BigInt(100 - CONFIG.SLIPPAGE)) / 100n).toString();
            const deadline = Math.floor(Date.now() / 1000) + (CONFIG.DEADLINE_MINUTES * 60);

            // Execute swap
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

            console.log(chalk.green("Transaction sent:", tx.hash));
            console.log(chalk.blue("Amount:", CONFIG.SWAP_AMOUNT, "ETH"));

            // Wait for confirmation and display results
            const receipt = await tx.wait();
            console.log(chalk.green("Transaction confirmed! Gas used:", receipt.gasUsed.toString()));

            // Handle delay between transactions
            if (i < CONFIG.TOTAL_TRANSACTIONS - 1) {
                console.log(chalk.yellow(`Waiting ${CONFIG.DELAY_MINUTES} minutes until next transaction...\n`));
                await countdown(CONFIG.DELAY_MINUTES);
            }
        } catch (error) {
            console.error(chalk.red(`Transaction ${i + 1} failed:`), error.message);
            console.log(chalk.yellow('Retrying in 1 minute...'));
            await sleep(1);
        }
    }
}

// Script Execution
swapExactETHForTokens()
    .then(() => {
        console.log(chalk.green("\n=== All transactions completed successfully ==="));
        process.exit(0);
    })
    .catch(error => {
        console.error(chalk.red("\nScript execution error:"), error.message);
        process.exit(1);
    });
