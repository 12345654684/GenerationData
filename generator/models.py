from django.db import models
import json

class GenerationLog(models.Model):
    """数据生成操作日志模型"""
    ip_address = models.CharField(max_length=50, verbose_name="操作IP")
    database_name = models.CharField(max_length=100, verbose_name="目标数据库")
    table_name = models.CharField(max_length=100, verbose_name="目标表名")
    generation_count = models.IntegerField(verbose_name="生成数量")
    start_date = models.CharField(max_length=20, verbose_name="开始日期")
    end_date = models.CharField(max_length=20, verbose_name="结束日期")
    # 存储造数规则（JSON格式）
    generation_rules = models.TextField(verbose_name="造数规则")
    operation_time = models.DateTimeField(auto_now_add=True, verbose_name="操作时间")
    status = models.BooleanField(default=True, verbose_name="操作状态")
    error_msg = models.TextField(blank=True, null=True, verbose_name="错误信息")

    class Meta:
        verbose_name = "数据生成日志"
        verbose_name_plural = "数据生成日志"
        ordering = ["-operation_time"]

    def __str__(self):
        return f"{self.ip_address} 在 {self.operation_time} 操作了 {self.database_name}.{self.table_name}"

    def set_rules(self, rules_dict):
        """将字典格式的规则转换为JSON字符串存储"""
        self.generation_rules = json.dumps(rules_dict, ensure_ascii=False, indent=2)

    def get_rules(self):
        """将JSON字符串转换为字典"""
        return json.loads(self.generation_rules) if self.generation_rules else {}