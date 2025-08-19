#!/usr/bin/env node

/**
 * Convert HTML wireframes to PNG images
 * Requires: npm install puppeteer
 */

const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

async function convertWireframesToImages() {
    const browser = await puppeteer.launch();
    const page = await browser.newPage();
    
    // Set viewport for consistent screenshots
    await page.setViewport({ width: 1200, height: 800 });
    
    const htmlFiles = [
        'create_english_wireframes.html',
        'admin_wireframes.html', 
        'public_and_workflow_wireframes.html',
        'final_wireframes.html'
    ];
    
    // Screen IDs to extract
    const screenIds = [
        'REG-001', 'REG-002', 'AUTH-001', 'AUTH-002', 'DASH-001',
        'ADMIN-001', 'ADMIN-002', 'ADMIN-003', 'ADMIN-004', 'ADMIN-005',
        'ADMIN-006', 'ADMIN-007', 'ADMIN-008',
        'PUB-001', 'PUB-002', 'PUB-003', 'SEARCH-001', 'LIC-001'
    ];
    
    for (const htmlFile of htmlFiles) {
        const filePath = path.join(__dirname, htmlFile);
        
        if (!fs.existsSync(filePath)) {
            console.log(`Skipping ${htmlFile} - file not found`);
            continue;
        }
        
        console.log(`Processing ${htmlFile}...`);
        
        await page.goto(`file://${filePath}`);
        
        // Extract wireframes from this file
        for (const screenId of screenIds) {
            try {
                const element = await page.$(`#${screenId}`);
                if (element) {
                    console.log(`  Capturing ${screenId}...`);
                    await element.screenshot({
                        path: `${screenId}-EN.png`,
                        quality: 90
                    });
                }
            } catch (error) {
                console.log(`  Failed to capture ${screenId}: ${error.message}`);
            }
        }
    }
    
    await browser.close();
    console.log('Conversion complete!');
}

// Check if puppeteer is available
try {
    require('puppeteer');
    convertWireframesToImages().catch(console.error);
} catch (error) {
    console.log('Puppeteer not installed. Install with: npm install puppeteer');
    console.log('Alternative: Use browser dev tools to manually screenshot each wireframe section');
}
