import {expect, test} from '@playwright/test';

test('user can move through primary navigation tabs', async ({page}) => {
  await page.goto('/');

  await expect(page.getByText(/Weekly Dashboard/i)).toBeVisible();

  await page.getByRole('button', {name: /Contacts/i}).click();
  await expect(page.getByText(/Household Members/i)).toBeVisible();

  await page.getByRole('button', {name: /Profile/i}).click();
  await expect(page.getByText(/Profile Settings/i)).toBeVisible();

  await page.getByRole('button', {name: /Alfred/i}).click();
  await expect(page.getByText(/Always at your service/i)).toBeVisible();
});
