-- 修正 stock_daily 中 ts_code 与 stock_name 错配（执行前请备份）。
-- 与 api/app/stock_display.py 中 CANONICAL_TS_CODE_TO_STOCK_NAME_ZH 保持一致。

USE `chat_bi_case`;

UPDATE `stock_daily` SET `stock_name` = '贵州茅台' WHERE `ts_code` = '600519.SH';
UPDATE `stock_daily` SET `stock_name` = '航天信息' WHERE `ts_code` = '600271.SH';
UPDATE `stock_daily` SET `stock_name` = '五粮液' WHERE `ts_code` = '000858.SZ';
UPDATE `stock_daily` SET `stock_name` = '广发证券' WHERE `ts_code` = '000776.SZ';
UPDATE `stock_daily` SET `stock_name` = '中芯国际' WHERE `ts_code` = '688981.SH';
UPDATE `stock_daily` SET `stock_name` = '比亚迪' WHERE `ts_code` = '002594.SZ';
UPDATE `stock_daily` SET `stock_name` = '中兴通讯' WHERE `ts_code` = '000063.SZ';
